from dotenv import load_dotenv

from .cli import main

load_dotenv()


if __name__ == "__main__":
    raise SystemExit(main())
