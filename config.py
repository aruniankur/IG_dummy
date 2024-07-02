from celery import Celery, Task
from flask import Flask
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
CORS(app)
def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

app.config.from_mapping(
        CELERY=dict(
            broker_url="redis://localhost",
            result_backend="redis://localhost",
            task_ignore_result=True,
            broker_connection_retry_on_startup=True,
        ),
    )

app.config.from_prefixed_env()
celery_app = celery_init_app(app)

# Adding periodic task schedule configuration
celery_app.conf.beat_schedule = {
    'periodic-task-every-10-seconds': {
        'task': 'bgtasks.periodic_task',
        'schedule': 10.0,  # Run every 10 seconds
    },
}
    