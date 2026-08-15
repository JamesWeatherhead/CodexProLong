# Security

Do not commit provider keys, Arena credentials, browser cookies, Codex session
rollouts, or Paperclip credentials. Run:

```bash
python tools/secret_scan.py .
```

before every push. If a credential reaches git history, revoke it first and
then rewrite the affected history; deleting the current file is not enough.

Security or verifier-integrity reports should be sent privately to the
repository owner before public disclosure when exploitation could harm other
users.

