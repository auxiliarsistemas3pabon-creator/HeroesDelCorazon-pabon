from users.models import User

PASSWORD = "Demo-Pass-2026"
CRITERIA = ["META", "EFECTIVA", "PRODUCTIVIDAD", "IMPLEMENTA", "APRENDIZAJE", "RECEPTIVA", "RESPETA", "ESCUCHA", "FOMENTA", "INTERACCION", "CONOCIMIENTO", "DISPOSICION"]
ALL_SCORES = {c: 4 for c in CRITERIA}


def create_user(username, role, area="Emergency"):
    return User.objects.create_user(
        username=username, email=f"{username}@demo.com", password=PASSWORD,
        first_name="Demo", last_name="Fictional", role=role, area=area,
    )
