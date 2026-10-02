"""Settings repository."""

from domain.entities import Setting
from domain.repositories import AbstractSettingsRepository
from infrastructure import mappers
from infrastructure.models import Setting as ORMSetting
from repositories.base import AbstractRepository


class SettingsRepository(AbstractSettingsRepository, AbstractRepository):
    """Repository for settings."""

    def get(self, key: str) -> Setting | None:
        """Get a setting value as domain entity, or None if not stored."""
        orm = self.db.session.query(ORMSetting).filter_by(key=key).first()
        if orm:
            return mappers.map_setting(orm)
        return None

    def get_all(self) -> dict[str, str]:
        """Get all settings as a flat dict."""
        rows = self.db.session.query(ORMSetting).all()
        return {row.key: row.value for row in rows}

    def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.set_many({key: value})

    def set_many(self, values: dict[str, str]) -> None:
        """Write a batch atomically and leave the session usable on failure."""
        if not values:
            return
        session = self.db.session
        try:
            for key, value in values.items():
                setting = session.query(ORMSetting).filter_by(key=key).first()
                if setting:
                    setting.value = value
                else:
                    session.add(ORMSetting(key=key, value=value))
            self.commit()
        except Exception:
            session.rollback()
            raise
