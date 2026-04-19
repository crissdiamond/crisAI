import os
import requests
from dotenv import load_dotenv
from msal import PublicClientApplication

load_dotenv()

TENANT_ID = os.environ["MS_TENANT_ID"]
CLIENT_ID = os.environ["MS_CLIENT_ID"]
REDIRECT_URI = os.environ.get("MS_REDIRECT_URI", "http://localhost")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = [
    "User.Read",
    "Sites.Read.All",
    "Files.Read.All",
    
]

app = PublicClientApplication(
    client_id=CLIENT_ID,
    authority=AUTHORITY,
)

#result = app.acquire_token_interactive(
#    scopes=SCOPES,
#)

result = app.acquire_token_interactive(
    scopes=SCOPES,
    login_hint="your.upn@yourorg.ac.uk",
    domain_hint="organizations",
)

print("\nGranted scopes:")
print(result.get("scope"))

if "access_token" not in result:
    print("Login failed")
    print(result)
    raise SystemExit(1)

print("Login succeeded")
print("Account:", result.get("id_token_claims", {}).get("preferred_username"))

headers = {
    "Authorization": f"Bearer {result['access_token']}",
    "Accept": "application/json",
}

me = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=30)
print("\n/me status:", me.status_code)
print(me.text)

sites = requests.get("https://graph.microsoft.com/v1.0/sites?search=*", headers=headers, timeout=30)
print("\n/sites search status:", sites.status_code)
print(sites.text[:2000])

if "access_token" not in result:
    print("Login failed")
    from pprint import pprint
    pprint(result)
    raise SystemExit(1)

print("Login succeeded")
print("Account:", result.get("id_token_claims", {}).get("preferred_username"))
print("\nGranted scopes:")
print(result.get("scope"))

root_site = requests.get(
    "https://graph.microsoft.com/v1.0/sites/root",
    headers=headers,
    timeout=30,
)
print("\n/sites/root status:", root_site.status_code)
print(root_site.text[:2000])

sites = requests.get(
    "https://graph.microsoft.com/v1.0/sites?search=*",
    headers=headers,
    timeout=30,
)
print("\n/sites search status:", sites.status_code)
print(sites.text[:2000])

drives = requests.get(
    "https://graph.microsoft.com/v1.0/me/drives",
    headers=headers,
    timeout=30,
)
print("\n/me/drives status:", drives.status_code)
print(drives.text[:2000])
