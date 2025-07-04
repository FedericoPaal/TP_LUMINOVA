from django.apps import AppConfig


class AppLuminovaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "App_LUMINOVA"

    def ready(self):
        import App_LUMINOVA.signals
