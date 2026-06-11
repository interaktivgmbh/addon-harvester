import sys

from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/cloud-platform']


def main() -> int:
    credentials = service_account.Credentials.from_service_account_file(sys.argv[1], scopes=SCOPES)
    credentials.refresh(Request())
    print(credentials.token)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
