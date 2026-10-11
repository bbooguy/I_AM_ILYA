"""Загрузка и валидация пяти групп данных об SQL-инъекциях."""
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class IdentificationRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: Optional[str] = Field(default=None, alias="Title")
    category: Optional[str] = Field(default=None, alias="Category")
    attack_type: Optional[str] = Field(default=None, alias="Attack Type")


class AttackDescriptionRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    scenario_description: Optional[str] = Field(default=None, alias="Scenario Description")
    attack_steps: Optional[str] = Field(default=None, alias="Attack Steps")
    tools_used: Optional[str] = Field(default=None, alias="Tools Used")


class TargetVulnerabilityRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    target_type: Optional[str] = Field(default=None, alias="Target Type")
    vulnerability: Optional[str] = Field(default=None, alias="Vulnerability")
    mitre_technique: Optional[str] = Field(default=None, alias="MITRE Technique")


class ImpactProtectionRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    impact: Optional[str] = Field(default=None, alias="Impact")
    detection_method: Optional[str] = Field(default=None, alias="Detection Method")
    solution: Optional[str] = Field(default=None, alias="Solution")


class MetadataRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    tags: Optional[str] = Field(default=None, alias="Tags")
    source: Optional[str] = Field(default=None, alias="Source")


class APIClient:
    def __init__(self, base_url, login, password, timeout=120.0):
        self.client = httpx.Client(
            base_url=base_url, auth=(login, password), timeout=timeout
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.close()

    def _get_json(self, path) -> list[dict]:
        try:
            response = self.client.get(path)
        except httpx.TimeoutException as error:
            raise RuntimeError(f"Превышено время ожидания: {path}") from error
        except httpx.RequestError as error:
            raise RuntimeError(f"Ошибка соединения: {path}: {error}") from error

        messages = {401: "Неверный логин или пароль", 403: "Доступ запрещён",
                    404: "Эндпоинт не найден"}
        if response.status_code in messages:
            raise RuntimeError(f"{messages[response.status_code]}: {path}")
        if response.status_code >= 500:
            raise RuntimeError(f"Ошибка сервера {response.status_code}: {path}")
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as error:
            raise ValueError(f"Сервер вернул некорректный JSON: {path}") from error
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError(f"Ожидался список объектов: {path}")
        return data

    def fetch_identification(self) -> list[IdentificationRow]:
        return [IdentificationRow.model_validate(row)
                for row in self._get_json("/api/identification")]

    def fetch_attack_description(self) -> list[AttackDescriptionRow]:
        return [AttackDescriptionRow.model_validate(row)
                for row in self._get_json("/api/attack_description")]

    def fetch_target_vulnerability(self) -> list[TargetVulnerabilityRow]:
        return [TargetVulnerabilityRow.model_validate(row)
                for row in self._get_json("/api/target_vulnerability")]

    def fetch_impact_protection(self) -> list[ImpactProtectionRow]:
        return [ImpactProtectionRow.model_validate(row)
                for row in self._get_json("/api/impact_protection")]

    def fetch_metadata(self) -> list[MetadataRow]:
        return [MetadataRow.model_validate(row)
                for row in self._get_json("/api/metadata")]

    def fetch_all(self) -> pd.DataFrame:
        frames = []
        for fetch in (
            self.fetch_identification,
            self.fetch_attack_description,
            self.fetch_target_vulnerability,
            self.fetch_impact_protection,
            self.fetch_metadata,
        ):
            rows = fetch()
            if not rows:
                raise ValueError(f"Пустая группа: {fetch.__name__}")
            frame = pd.DataFrame([row.model_dump(by_alias=True) for row in rows])
            if frame["id"].duplicated().any():
                raise ValueError(f"Повторяющиеся id: {fetch.__name__}")
            frames.append(frame)
        merged = frames[0]
        for frame in frames[1:]:
            merged = pd.merge(merged, frame, on="id", how="inner", validate="one_to_one")
        return merged


if __name__ == "__main__":
    with APIClient("http://193.233.171.205:8000", "student", "student_pass") as api:
        df = api.fetch_all()
    output = Path(__file__).with_name("sql_injections_merged.csv")
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Сохранено {len(df)} строк, {len(df.columns)} столбцов: {output}")
