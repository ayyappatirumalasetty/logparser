import re

PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all\s+)?previous\s+instructions",
    r"(?i)ignore\s+(?:all\s+)?system\s+(?:prompt|instruction|rules)",
    r"(?i)bypass\s+(?:safety|system)\s+filters",
    r"(?i)you\s+are\s+now\s+unrestricted",
    r"(?i)do\s+anything\s+now\s*\(dan\)",
    r"(?i)developer\s+mode\s+enabled",
    r"(?i)override\s+system\s+prompt",
    r"(?i)ignore\s+guidelines\s+and\s+instructions",
    r"(?i)dan\s+mode\s+active",
]

SENSITIVE_PATTERNS = {
    "OpenAI API Key": re.compile(r"\bsk-[a-zA-Z0-9-_]{32,}\b"),
    "Generic Token": re.compile(r"\b(?:api[_-]?key|secret[_-]?token|auth[_-]?token|bearer)\b\s*[:=]\s*['\"]?([a-zA-Z0-9-_]{16,})['\"]?", re.IGNORECASE),
    "Database Password": re.compile(r"\b(mongodb|postgresql|postgres|mysql|mssql|redis|amqp|amqps)://([^:]+):([^@/]+)@", re.IGNORECASE),
    "AWS Key ID": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "AWS Secret Access Key": re.compile(r"\b(?:aws_secret|aws_secret_key|secret_key)\b\s*[:=]\s*['\"]?([a-zA-Z0-9+/]{40})['\"]?", re.IGNORECASE),
    "Credit Card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "Email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "Generic Password": re.compile(r"\b(?:password|passwd|pwd|passcode|secret)\b\s*[:=]\s*['\"]?([a-zA-Z0-9!@#$%^&*()_+=-]{6,30})['\"]?", re.IGNORECASE),
}

def detect_prompt_injection(text: str) -> bool:
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True
    return False

def redact_sensitive_info(text: str) -> str:
    sanitized = text
    
    # 1. Database Connection Strings (mongodb://user:pass@host)
    sanitized = SENSITIVE_PATTERNS["Database Password"].sub(r"\1://\2:[REDACTED]@", sanitized)
    
    # 2. OpenAI API Keys (sk-...)
    sanitized = SENSITIVE_PATTERNS["OpenAI API Key"].sub("sk-[REDACTED]", sanitized)
    
    # 3. AWS Key ID
    sanitized = SENSITIVE_PATTERNS["AWS Key ID"].sub("[REDACTED_AWS_KEY_ID]", sanitized)
    
    # 4. AWS Secret Access Key
    def redact_aws_secret(match):
        full_match = match.group(0)
        secret = match.group(1)
        return full_match.replace(secret, "[REDACTED_AWS_SECRET]")
    sanitized = SENSITIVE_PATTERNS["AWS Secret Access Key"].sub(redact_aws_secret, sanitized)
    
    # 5. Generic Token/Secret
    def redact_generic_token(match):
        full_match = match.group(0)
        token = match.group(1)
        return full_match.replace(token, "[REDACTED]")
    sanitized = SENSITIVE_PATTERNS["Generic Token"].sub(redact_generic_token, sanitized)
    
    # 6. Credit Card
    sanitized = SENSITIVE_PATTERNS["Credit Card"].sub("[REDACTED_CREDIT_CARD]", sanitized)
    
    # 7. Email
    sanitized = SENSITIVE_PATTERNS["Email"].sub("[REDACTED_EMAIL]", sanitized)
    
    # 8. Generic Password
    def redact_generic_password(match):
        full_match = match.group(0)
        password = match.group(1)
        return full_match.replace(password, "[REDACTED]")
    sanitized = SENSITIVE_PATTERNS["Generic Password"].sub(redact_generic_password, sanitized)
    
    return sanitized

def validate_and_sanitize(issue_context: str, entries_txt: str) -> tuple[str, str]:
    if detect_prompt_injection(issue_context):
        raise ValueError("Safety Alert: Potential prompt injection or jailbreak attempt detected in issue context.")
    
    if detect_prompt_injection(entries_txt):
        raise ValueError("Safety Alert: Potential prompt injection or jailbreak attempt detected in log entries.")
        
    clean_context = redact_sensitive_info(issue_context)
    clean_entries = redact_sensitive_info(entries_txt)
    
    return clean_context, clean_entries
