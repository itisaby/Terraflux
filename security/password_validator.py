"""
Password Strength Validation
Enforces strong password requirements
"""
import re
from typing import Tuple, List


class PasswordValidator:
    """Validate password strength and enforce security policies"""

    # Common weak passwords to reject
    COMMON_PASSWORDS = {
        'password', 'password123', 'password1', '12345678', 'qwerty123',
        'admin123', 'welcome123', 'abc123456', 'letmein123', 'monkey123',
        'iloveyou', 'trustno1', 'dragon123', 'master123', 'sunshine',
        'password1234', 'admin1234', 'qwerty1234', 'welcome1234'
    }

    def __init__(
        self,
        min_length: int = 12,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True
    ):
        """
        Initialize password validator

        Args:
            min_length: Minimum password length
            require_uppercase: Require at least one uppercase letter
            require_lowercase: Require at least one lowercase letter
            require_digit: Require at least one digit
            require_special: Require at least one special character
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def validate(self, password: str, username: str = None) -> Tuple[bool, str]:
        """
        Validate password strength

        Args:
            password: Password to validate
            username: Optional username to check similarity

        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message will be empty string
        """
        errors = []

        # Check minimum length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")

        # Check uppercase requirement
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        # Check lowercase requirement
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        # Check digit requirement
        if self.require_digit and not re.search(r'\d', password):
            errors.append("Password must contain at least one number")

        # Check special character requirement
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/~`]', password):
            errors.append("Password must contain at least one special character")

        # Check against common passwords
        if password.lower() in self.COMMON_PASSWORDS:
            errors.append("Password is too common. Please choose a stronger password")

        # Check password doesn't contain username
        if username and len(username) >= 3:
            if username.lower() in password.lower():
                errors.append("Password cannot contain your username")

        # Check for sequential characters (123, abc, etc.)
        if self._has_sequential_chars(password):
            errors.append("Password contains sequential characters. Please choose a more complex password")

        # Check for repeated characters (aaa, 111, etc.)
        if self._has_repeated_chars(password):
            errors.append("Password contains too many repeated characters")

        if errors:
            return False, "; ".join(errors)

        return True, ""

    def _has_sequential_chars(self, password: str, threshold: int = 4) -> bool:
        """
        Check if password contains sequential characters

        Args:
            password: Password to check
            threshold: Length of sequential characters to trigger (default: 4)

        Returns:
            True if sequential characters found
        """
        # Check for numeric sequences
        for i in range(len(password) - threshold + 1):
            substr = password[i:i + threshold]
            if substr.isdigit():
                chars = [int(c) for c in substr]
                # Check ascending
                if all(chars[j] == chars[j-1] + 1 for j in range(1, len(chars))):
                    return True
                # Check descending
                if all(chars[j] == chars[j-1] - 1 for j in range(1, len(chars))):
                    return True

        # Check for alphabetic sequences
        for i in range(len(password) - threshold + 1):
            substr = password[i:i + threshold].lower()
            if substr.isalpha():
                chars = [ord(c) for c in substr]
                # Check ascending
                if all(chars[j] == chars[j-1] + 1 for j in range(1, len(chars))):
                    return True
                # Check descending
                if all(chars[j] == chars[j-1] - 1 for j in range(1, len(chars))):
                    return True

        return False

    def _has_repeated_chars(self, password: str, threshold: int = 3) -> bool:
        """
        Check if password has too many repeated characters

        Args:
            password: Password to check
            threshold: Number of repeated characters to trigger (default: 3)

        Returns:
            True if repeated characters found
        """
        for i in range(len(password) - threshold + 1):
            if len(set(password[i:i + threshold])) == 1:
                return True
        return False

    def generate_requirements_text(self) -> str:
        """
        Generate human-readable text describing password requirements

        Returns:
            String describing requirements
        """
        requirements = [f"At least {self.min_length} characters long"]

        if self.require_uppercase:
            requirements.append("At least one uppercase letter")
        if self.require_lowercase:
            requirements.append("At least one lowercase letter")
        if self.require_digit:
            requirements.append("At least one number")
        if self.require_special:
            requirements.append("At least one special character")

        requirements.extend([
            "Cannot be a common password",
            "Cannot contain sequential characters (e.g., '1234', 'abcd')",
            "Cannot have repeated characters (e.g., 'aaa', '111')"
        ])

        return "Password requirements:\n- " + "\n- ".join(requirements)


# Default validator instance
default_validator = PasswordValidator(
    min_length=12,
    require_uppercase=True,
    require_lowercase=True,
    require_digit=True,
    require_special=True
)


def validate_password_strength(password: str, username: str = None) -> Tuple[bool, str]:
    """
    Convenience function to validate password using default validator

    Args:
        password: Password to validate
        username: Optional username to check similarity

    Returns:
        Tuple of (is_valid, error_message)
    """
    return default_validator.validate(password, username)
