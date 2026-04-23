import random
import uuid
from datetime import datetime, timezone


NORMAL_EVENTS = [
    ("auth", "successful login from known device"),
    ("dns", "internal service discovery request"),
    ("vpn", "routine session refresh"),
    ("edr", "scheduled endpoint scan completed"),
    ("cloud", "service account listed storage buckets"),
    ("proxy", "developer workstation downloaded package metadata"),
]

ATTACK_CHAIN = [
    ("auth", "failed login burst against finance-admin from 185.199.110.77"),
    ("auth", "successful login for finance-admin after password spray"),
    ("cloud", "new access key created for finance-admin"),
    ("dns", "beacon-like requests to paste-sync-cdn.net every 9 seconds"),
    ("edr", "powershell encoded command launched by office updater"),
    ("iam", "finance-admin added external principal to billing-reader"),
    ("proxy", "large archive uploaded to filedrop-api.net from finance subnet"),
]

USERS = ["finance-admin", "svc-backup", "mira.rao", "jules.chen", "hr-payroll", "svc-ci"]
HOSTS = ["fin-ledger-02", "vpn-gw-1", "hr-laptop-18", "cloud-iam", "build-runner-7", "mail-edge-3"]


class LogGenerator:
    def __init__(self) -> None:
        self.tick = 0
        self.attack_index = 0
        self.attack_active = False

    def force_attack(self) -> None:
        self.attack_active = True
        self.attack_index = 0

    def next_log(self) -> dict:
        self.tick += 1
        if self.tick % 13 == 0:
            self.attack_active = True

        if self.attack_active and self.attack_index < len(ATTACK_CHAIN):
            source, message = ATTACK_CHAIN[self.attack_index]
            self.attack_index += 1
            if self.attack_index == len(ATTACK_CHAIN):
                self.attack_active = False
            severity = random.choice(["medium", "high", "critical"])
        else:
            source, message = random.choice(NORMAL_EVENTS)
            severity = random.choice(["low", "low", "info", "medium"])

        return {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "host": random.choice(HOSTS),
            "user": "finance-admin" if "finance-admin" in message else random.choice(USERS),
            "ip": self._ip(message),
            "severity": severity,
            "message": message,
        }

    def _ip(self, message: str) -> str:
        if "185.199.110.77" in message:
            return "185.199.110.77"
        return random.choice(["10.4.12.8", "10.4.18.44", "172.16.9.21", "34.91.77.3"])
