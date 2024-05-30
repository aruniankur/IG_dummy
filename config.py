from celery import Celery, Task
from flask import Flask

app = Flask(__name__, template_folder='templates')
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
            broker_url="rediss://red-cpaknacf7o1s73ai68og:JZshvN5SXUfCQL4D5i3AJIBM0RSKhWxy@singapore-redis.render.com:6379/0?ssl_cert_reqs=CERT_NONE",
            result_backend="rediss://red-cpaknacf7o1s73ai68og:JZshvN5SXUfCQL4D5i3AJIBM0RSKhWxy@singapore-redis.render.com:6379/0?ssl_cert_reqs=CERT_NONE",
            task_ignore_result=True,
            broker_connection_retry_on_startup=True,
        ),
    )
app.config.from_prefixed_env()
celery_init_app(app)
    