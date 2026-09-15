from pathlib import Path

from joblib.numpy_pickle import NumpyUnpickler, _validate_fileobject_and_memmap

from my_service.model import (
    SequencePreprocessor,
    TinySequenceEncoder,
    TinyTransformerClassifier,
)


class ModelUnpickler(NumpyUnpickler):
    def find_class(self, module, name):
        # Старый артефакт сохранён из ноутбука, где классы жили в __main__.
        classes = {
            cls.__name__: cls
            for cls in (
                SequencePreprocessor,
                TinySequenceEncoder,
                TinyTransformerClassifier,
            )
        }
        if module == "__main__" and name in classes:
            return classes[name]
        return super().find_class(module, name)


def load_model(path: str | Path):
    filename = str(path)
    with open(filename, "rb") as file:
        with _validate_fileobject_and_memmap(file, filename) as (stream, _):
            return ModelUnpickler(
                filename, stream, ensure_native_byte_order=True
            ).load()
