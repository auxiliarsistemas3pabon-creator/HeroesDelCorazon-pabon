from getpass import getpass
import sys

from django.core.management.base import BaseCommand, CommandError

from users.models import User


class Command(BaseCommand):
    """Crea un colaborador pidiendo la contrasena por terminal, para no exponerla en argumentos ni en el historial del shell."""
    help = "Create a collaborator account with an interactively entered password."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Document number used to sign in.")
        parser.add_argument("first_name", help="Collaborator's first name or display name.")
        parser.add_argument("--last-name", default="", help="Collaborator's last name.")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            raise CommandError(f"A user with username {username} already exists.")

        if not sys.stdin.isatty():
            raise CommandError("Run this command in an interactive terminal to enter the password securely.")

        password = getpass("Password: ")
        confirmation = getpass("Password (again): ")
        if not password:
            raise CommandError("Password cannot be empty.")
        if password != confirmation:
            raise CommandError("The two passwords did not match.")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=options["first_name"],
            last_name=options["last_name"],
            role=User.Role.COLLABORATOR,
        )
        self.stdout.write(self.style.SUCCESS(f"Collaborator created: {user.username}"))
