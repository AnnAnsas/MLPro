"""Проверка данных, переобучение с гейтом и выкат нового champion."""

from datetime import UTC, datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import CronTriggerTimetable, Param, dag, task
from kubernetes.client import models as k8s

PULL_DATA = "uv run --no-sync dvc pull -r cluster dataset/sensor_trends.csv"
MLFLOW_URI = "http://mlflow.mlops:5000"
S3_ENV = [k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))]
RESOURCES = k8s.V1ResourceRequirements(
    requests={"cpu": "250m", "memory": "512Mi"},
    limits={"cpu": "1", "memory": "1Gi"},
)


@dag(
    schedule=CronTriggerTimetable("0 3 * * *", timezone="Europe/Moscow"),
    catchup=False,
    params={
        "epochs": Param(8, type="integer", minimum=1, maximum=30,
                        description="Число эпох Tiny Transformer"),
    },
    tags=["my-service"],
)
def my_service_retrain():
    validate = KubernetesPodOperator(
        task_id="validate",
        name="my-service-validate",
        namespace="mlops",
        in_cluster=True,
        image="{{ var.value.my_service_image }}",
        image_pull_policy="IfNotPresent",
        cmds=["sh", "-c", f"{PULL_DATA} && uv run --no-sync python -m my_service.validate_data"],
        env_vars={"MLFLOW_TRACKING_URI": MLFLOW_URI},
        env_from=S3_ENV,
        container_resources=RESOURCES,
        get_logs=True,
        on_finish_action="delete_pod",
    )

    train = KubernetesPodOperator(
        task_id="train",
        name="my-service-train",
        namespace="mlops",
        in_cluster=True,
        image="{{ var.value.my_service_image }}",
        image_pull_policy="IfNotPresent",
        cmds=["sh", "-c", f"{PULL_DATA} && uv run --no-sync python -m my_service.train"],
        env_vars={
            "MLFLOW_TRACKING_URI": MLFLOW_URI,
            "EPOCHS": "{{ params.epochs }}",
            "MODEL_OUTPUT": "/tmp/my-service.joblib",
        },
        env_from=S3_ENV,
        container_resources=RESOURCES,
        do_xcom_push=True,
        get_logs=True,
        on_finish_action="delete_pod",
    )

    @task.short_circuit
    def promoted(result: dict) -> bool:
        print(
            f"версия {result['version']}, validation_f1 {result['validation_f1']}, "
            f"champion до запуска {result['champion_before']}"
        )
        return bool(result["promoted"])

    @task
    def rollout() -> None:
        from kubernetes import client, config

        config.load_incluster_config()
        now = datetime.now(UTC).isoformat()
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": now},
                    }
                }
            }
        }
        client.AppsV1Api().patch_namespaced_deployment("my-service", "default", body)
        print("my-service перезапущен", now)

    validate >> train
    promoted(train.output) >> rollout()


my_service_retrain()
