"""Entrypoint para empaquetar con PyInstaller (import absoluto del paquete)."""
import sys

from actas.app import main

if __name__ == "__main__":
    sys.exit(main())
