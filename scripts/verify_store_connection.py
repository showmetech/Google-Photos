"""Read-only Store authentication check. Never logs tokens or response bodies."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(url, *, body=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # The identity endpoint can echo credential-related details in its body.
        stage = "authentication" if body is not None else "product/submission read"
        raise RuntimeError(f"Store {stage} failed: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Store connection check failed: network unavailable") from None


def main():
    required = ("TENANT", "CLIENT", "CLIENT_SECRET", "PRODUCT", "IDENTITY")
    if any(not os.environ.get(key) for key in required):
        raise RuntimeError("Store connection check: required configuration missing")
    tenant, client, product = (os.environ[key] for key in ("TENANT", "CLIENT", "PRODUCT"))
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", tenant):
        raise RuntimeError("Invalid tenant identifier")
    if not re.fullmatch(r"[A-Z0-9]{12}", product):
        raise RuntimeError("Invalid product identifier")
    expected = json.loads(os.environ["IDENTITY"])
    if expected.get("productId") != product:
        raise RuntimeError("Store product configuration mismatch")
    auth = request_json(f"https://login.microsoftonline.com/{tenant}/oauth2/token", body={
        "grant_type": "client_credentials", "client_id": client,
        "client_secret": os.environ["CLIENT_SECRET"],
        "resource": "https://manage.devcenter.microsoft.com",
    })
    token = auth["access_token"]
    print("Microsoft Entra authentication succeeded; checking Store product access")
    base = f"https://manage.devcenter.microsoft.com/v1.0/my/applications/{product}"
    app = request_json(base, token=token)
    if app.get("id") != product or app.get("packageIdentityName") != expected.get("name"):
        raise RuntimeError("Authenticated Store product identity mismatch")
    if app.get("publisherName") != expected.get("publisher"):
        raise RuntimeError("Authenticated Store publisher mismatch")
    result = {"productId": product, "identityVerified": True, "submissions": []}
    for field in ("lastPublishedApplicationSubmission", "pendingApplicationSubmission"):
        submission_id = (app.get(field) or {}).get("id")
        if not submission_id:
            continue
        if not str(submission_id).isdigit():
            raise RuntimeError("Invalid submission identifier returned by Store")
        submission = request_json(f"{base}/submissions/{submission_id}", token=token)
        result["submissions"].append({
            "kind": field, "id": str(submission_id), "status": submission.get("status"),
            "packageVersions": sorted({p.get("version", "") for p in submission.get("applicationPackages", [])}),
        })
    print(json.dumps(result, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as report:
            report.write("## Read-only Store connection verified\n\n```json\n" + json.dumps(result, indent=2) + "\n```\nNo submission was created, changed, or cancelled.\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, KeyError) as exc:
        # Do not dump exception chains or request/response objects.
        print(str(exc) if isinstance(exc, RuntimeError) else "Invalid Store response/configuration", file=sys.stderr)
        sys.exit(1)
