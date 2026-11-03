from django.core.management.base import BaseCommand

from users.models import User

# Nombres de prueba; se combinan para tener varias personas por área.
FIRST_NAMES = ["Marta", "Julián", "Paola", "Ricardo", "Sandra", "Hernán", "Lucía", "Mateo"]
LAST_NAMES = ["Ortiz Salazar", "Cano Restrepo", "Duque Arias", "Pineda Mejía", "Londoño Vega", "Zapata Ríos"]


class Command(BaseCommand):
    """Crea personal de prueba (rol personal): gente común que se evalúa, que no es colaborador, jefe ni administrador."""
    help = "Create test staff members (role personal) for every existing area. Safe to run again."

    def add_arguments(self, parser):
        parser.add_argument("--per-area", type=int, default=5, help="Staff members to create in each area (default 5).")

    def handle(self, *args, **options):
        areas = sorted(
            set(User.objects.filter(role__in=[User.Role.COLLABORATOR, User.Role.PERSONAL]).exclude(area="").values_list("area", flat=True))
        )
        created = 0
        for area_number, area in enumerate(areas, start=1):
            for number in range(options["per_area"]):
                username = f"P{area_number:02d}{number + 1:02d}"
                if User.objects.filter(username=username).exists():
                    continue
                user = User(
                    username=username,
                    first_name=FIRST_NAMES[(area_number + number) % len(FIRST_NAMES)],
                    last_name=LAST_NAMES[(area_number * 2 + number) % len(LAST_NAMES)],
                    role=User.Role.PERSONAL,
                    area=area,
                    position="Personal de prueba",
                )
                user.set_unusable_password()  # se evalúa, no inicia sesión
                user.save()
                created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} personal de prueba creado en {len(areas)} áreas."))
