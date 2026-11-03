# Areas historicas que ya no se aceptan (se unificaron en "Sistemas"). Se guardan en casefold.
REMOVED_AREA_NAMES = frozenset({"sistema"})


def is_removed_area(value: str) -> bool:
    """True si el nombre corresponde a un area retirada; ignora espacios y mayusculas."""
    return value.strip().casefold() in REMOVED_AREA_NAMES
