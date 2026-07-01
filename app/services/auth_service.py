from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.db.session import engine


VALID_ROLES = {"admin", "engineer", "viewer"}
PUBLIC_USER_FIELDS = (
    "username",
    "role",
    "is_active",
    "created_at",
    "updated_at",
)


class AuthService:
    def authenticate_user(
        self,
        username: str,
        password: str,
    ) -> dict | None:
        user = self._get_user_record(username)
        if user is None or not user["is_active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return self._public_user(user)

    def get_user_by_username(self, username: str) -> dict | None:
        user = self._get_user_record(username)
        return self._public_user(user) if user else None

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "viewer",
    ) -> dict:
        normalized_username = self._normalize_username(username)
        normalized_role = self._validate_role(role)
        if len(password) < 8:
            raise ValueError("密码长度不能少于 8 个字符")

        query = text("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (:username, :password_hash, :role, true)
            RETURNING username, role, is_active, created_at, updated_at
        """)
        try:
            with engine.begin() as conn:
                row = conn.execute(
                    query,
                    {
                        "username": normalized_username,
                        "password_hash": hash_password(password),
                        "role": normalized_role,
                    },
                ).mappings().one()
        except IntegrityError as exc:
            raise ValueError(f"用户已存在: {normalized_username}") from exc

        return dict(row)

    def list_users(self) -> list[dict]:
        query = text("""
            SELECT username, role, is_active, created_at, updated_at
            FROM users
            ORDER BY created_at ASC, id ASC
        """)
        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]

    def _get_user_record(self, username: str) -> dict | None:
        normalized_username = username.strip() if username else ""
        if not normalized_username:
            return None

        query = text("""
            SELECT
                username, password_hash, role, is_active,
                created_at, updated_at
            FROM users
            WHERE username = :username
            LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(
                query,
                {"username": normalized_username},
            ).mappings().first()
        return dict(row) if row else None

    def _public_user(self, user: dict) -> dict:
        return {
            field: user.get(field)
            for field in PUBLIC_USER_FIELDS
        }

    def _normalize_username(self, username: str) -> str:
        normalized = username.strip() if username else ""
        if not normalized:
            raise ValueError("用户名不能为空")
        if len(normalized) > 100:
            raise ValueError("用户名长度不能超过 100")
        return normalized

    def _validate_role(self, role: str) -> str:
        normalized = role.strip().lower() if role else "viewer"
        if normalized not in VALID_ROLES:
            raise ValueError(
                f"无效角色: {role}。可选值: {sorted(VALID_ROLES)}"
            )
        return normalized
