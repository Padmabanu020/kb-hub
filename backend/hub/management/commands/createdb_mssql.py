from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the MSSQL database configured in settings if it does not exist."

    def handle(self, *args, **opts):
        import pyodbc
        db = settings.DATABASES["default"]
        if "mssql" not in db["ENGINE"]:
            raise CommandError("DB_ENGINE is not mssql.")
        o = db["OPTIONS"]
        auth = "Trusted_Connection=yes;" if "Trusted_Connection" in o.get("extra_params", "") \
            else f"UID={db['USER']};PWD={db['PASSWORD']};"
        server = db["HOST"] + (f",{db['PORT']}" if db["PORT"] else "")
        conn_str = (f"DRIVER={{{o['driver']}}};SERVER={server};DATABASE=master;"
                    f"{auth}TrustServerCertificate=yes")
        conn = pyodbc.connect(conn_str, autocommit=True)
        name = db["NAME"].replace("]", "]]")
        conn.execute(f"IF DB_ID(N'{db['NAME']}') IS NULL CREATE DATABASE [{name}]")
        conn.close()
        self.stdout.write(self.style.SUCCESS(f"Database '{db['NAME']}' is ready."))