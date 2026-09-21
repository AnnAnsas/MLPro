import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin
from sklearn.utils.validation import check_is_fitted
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


def validate_sequences(X):
    X = np.asarray(X, dtype=np.float32)
    if X.ndim != 3 or any(d == 0 for d in X.shape):
        raise ValueError("Ожидается непустой массив (N, T, F)")
    if np.isinf(X).any():
        raise ValueError("Бесконечности не допускаются; пропуски обозначайте NaN")
    return X


class SequencePreprocessor(TransformerMixin, BaseEstimator):
    def fit(self, X, y=None):
        X = validate_sequences(X)
        self.sequence_length_ = X.shape[1]
        self.n_features_in_ = X.shape[2]
        if np.isnan(X).all(axis=(0, 1)).any():
            raise ValueError("Есть полностью пустой канал в train")
        self.mean_ = np.nanmean(X, axis=(0, 1), keepdims=True)
        std = np.nanstd(X, axis=(0, 1), keepdims=True)
        self.scale_ = np.where(std < 1e-6, 1.0, std)
        return self

    def transform(self, X):
        check_is_fitted(self, ["mean_", "scale_"])
        X = validate_sequences(X)
        if X.shape[1:] != (self.sequence_length_, self.n_features_in_):
            raise ValueError("Неверная длина последовательности или число признаков")
        filled = np.where(np.isnan(X), self.mean_, X)
        return np.ascontiguousarray((filled - self.mean_) / self.scale_, dtype=np.float32)

class TinySequenceEncoder(nn.Module):
    def __init__(self, n_features, seq_len, d_model=24, nhead=4,
                 num_layers=2, dim_feedforward=48, dropout=0.1):
        super().__init__()
        self.projection = nn.Linear(n_features, d_model)
        self.positions = nn.Parameter(torch.empty(1, seq_len, d_model))
        nn.init.normal_(self.positions, std=0.02)
        # Отдельные экземпляры слоёв получают независимую инициализацию.
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
                dropout=dropout, activation="gelu", batch_first=True)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x):
        h = self.projection(x) + self.positions
        for layer in self.layers:
            h = layer(h)
        return self.head(self.norm(h).mean(dim=1)).squeeze(-1)


class TinyTransformerClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, d_model=24, nhead=4, num_layers=2,
                 dim_feedforward=48, dropout=0.1, epochs=8,
                 batch_size=64, lr=0.002, weight_decay=0.0001,
                 threshold=0.5, random_state=42):
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.dim_feedforward = dim_feedforward
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.weight_decay = weight_decay
        self.threshold = threshold
        self.random_state = random_state

    def fit(self, X, y):
        X = validate_sequences(X)
        y = np.asarray(y)
        if y.ndim != 1 or len(y) != len(X) or not np.array_equal(np.unique(y), [0, 1]):
            raise ValueError("y должен содержать оба класса 0 и 1 и совпадать с X по длине")
        if not np.isfinite(X).all():
            raise ValueError("Перед моделью нужен preprocessing")
        if self.epochs < 1 or self.batch_size < 1 or self.d_model % self.nhead:
            raise ValueError("Неверные epochs/batch_size или d_model не кратен nhead")
        torch.manual_seed(self.random_state)
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = X.shape[2]
        self.sequence_length_ = X.shape[1]
        self.model_ = TinySequenceEncoder(
            self.n_features_in_, self.sequence_length_, self.d_model,
            self.nhead, self.num_layers, self.dim_feedforward, self.dropout).cpu()
        dataset = TensorDataset(torch.from_numpy(np.ascontiguousarray(X)),
                                torch.tensor(y, dtype=torch.float32))
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True,
                            num_workers=0,
                            generator=torch.Generator().manual_seed(self.random_state))
        optimizer = torch.optim.AdamW(self.model_.parameters(), lr=self.lr,
                                      weight_decay=self.weight_decay)
        criterion = nn.BCEWithLogitsLoss()
        self.loss_history_ = []
        for epoch in range(self.epochs):
            self.model_.train()
            total = 0.0
            for xb, yb in loader:
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(self.model_(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model_.parameters(), 1.0)
                optimizer.step()
                total += loss.item() * len(xb)
            self.loss_history_.append(total / len(X))
            print(f"epoch {epoch+1:02d}/{self.epochs}: loss={self.loss_history_[-1]:.4f}")
        self.model_.eval()
        return self

    def predict_proba(self, X):
        check_is_fitted(self, ["model_", "classes_"])
        X = validate_sequences(X)
        if X.shape[1:] != (self.sequence_length_, self.n_features_in_):
            raise ValueError("Неверная форма входа")
        if not np.isfinite(X).all():
            raise ValueError("Перед моделью нужен preprocessing")
        self.model_.eval()
        chunks = []
        with torch.inference_mode():
            for start in range(0, len(X), self.batch_size):
                xb = torch.from_numpy(np.ascontiguousarray(X[start:start+self.batch_size]))
                chunks.append(torch.sigmoid(self.model_(xb)).numpy())
        p1 = np.concatenate(chunks)
        return np.column_stack([1.0-p1, p1])

    def predict(self, X):
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold должен быть в [0, 1]")
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(np.int64)
