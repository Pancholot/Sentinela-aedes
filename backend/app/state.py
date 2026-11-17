"""Estado del proceso (inicialización y simulador)."""
from dataclasses import dataclass


@dataclass
class AppState:
    ready: bool = False
    init_error: str | None = None
    simulator: object | None = None


app_state = AppState()
