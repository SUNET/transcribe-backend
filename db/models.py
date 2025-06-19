from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
from sqlalchemy.types import Enum as SQLAlchemyEnum
from sqlmodel import Field
from enum import Enum
from sqlmodel import SQLModel
import json


class JobStatusEnum(str, Enum):
    """
    Enum representing the status of a job.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(BaseModel):
    status: JobStatusEnum
    error: Optional[str] = None


class OutputFormatEnum(str, Enum):
    """
    Enum representing the output format of the transcription.
    """

    TXT = "txt"
    SRT = "srt"
    CSV = "csv"


class JobType(str, Enum):
    """
    Enum representing the type of job.
    """

    TRANSCRIPTION = "transcription"


class JobResult(SQLModel, table=True):
    """
    Model representing the result of a job.
    """

    __tablename__ = "job_results"

    id: Optional[int] = Field(default=None, primary_key=True, description="Primary key")
    job_id: str = Field(
        index=True,
        unique=True,
        description="UUID of the job",
    )
    user_id: str = Field(
        index=True,
        description="User ID associated with the job",
    )
    result: Optional[str] = Field(
        default=None,
        description="JSON formatted transcription result",
    )
    result_srt: Optional[str] = Field(
        default=None,
        description="SRT formatted transcription result",
    )

    def as_dict(self) -> dict:
        """
        Convert the job result object to a dictionary.
        Returns:
            dict: The job result object as a dictionary.
        """
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "result": self.result,
            "result_srt": self.result_srt,
        }


class Job(SQLModel, table=True):
    """
    Model representing a job in the system.
    """

    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True, description="Primary key")
    uuid: str = Field(
        default_factory=lambda: str(uuid4()),
        index=True,
        unique=True,
        description="UUID of the job",
    )
    user_id: Optional[str] = Field(
        default=None,
        index=True,
        description="User ID associated with the job",
    )
    status: JobStatusEnum = Field(
        default=None,
        sa_column=Field(sa_column=SQLAlchemyEnum(JobStatusEnum)),
        description="Current status of the job",
    )
    job_type: JobType = Field(
        default=None,
        sa_column=Field(sa_column=SQLAlchemyEnum(JobType)),
        description="Type of the job",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"onupdate": datetime.utcnow},
        default_factory=datetime.utcnow,
        description="Last updated timestamp",
    )
    language: str = Field(default="Swedish", description="Language used for the job")
    model_type: str = Field(default="base", description="Model type used for the job")
    speakers: Optional[str] = Field(
        default=None, description="Number of speakers in the audio"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")
    filename: str = Field(default="", description="Filename of the audio file")
    output_format: OutputFormatEnum = Field(
        default=OutputFormatEnum.TXT,
        sa_column=Field(sa_column=SQLAlchemyEnum(OutputFormatEnum)),
        description="Output format of the transcription",
    )

    def as_dict(self) -> dict:
        """
        Convert the job object to a dictionary.
        Returns:
            dict: The job object as a dictionary.
        """
        return {
            "id": self.id,
            "uuid": self.uuid,
            "user_id": self.user_id,
            "status": self.status,
            "job_type": self.job_type,
            "created_at": str(self.created_at),
            "updated_at": str(self.updated_at),
            "language": self.language,
            "model_type": self.model_type,
            "filename": self.filename,
            "speakers": self.speakers,
            "output_format": self.output_format,
            "error": self.error,
        }


class Jobs(BaseModel):
    """
    Model representing a list of jobs.
    """

    jobs: List[Job]


class User(SQLModel, table=True):
    """
    Model representing a user in the system.
    """

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True, description="Primary key")
    user_id: str = Field(
        default=None,
        index=True,
        description="User ID",
    )
    username: str = Field(
        default=None,
        index=True,
        description="Username of the user",
    )
    realm: str = Field(
        default=None,
        index=True,
        description="User realm",
    )
    admin: bool = Field(
        default=False,
        description="Indicates if the user is an admin",
    )
    transcribed_seconds: int = Field(
        default=None,
        description="Transcribed seconds",
    )
    last_login: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last login timestamp",
    )

    def as_dict(self) -> dict:
        """
        Convert the user object to a dictionary.
        Returns:
            dict: The user object as a dictionary.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "realm": self.realm,
            "admin": self.admin,
            "transcribed_seconds": self.transcribed_seconds,
            "last_login": str(self.last_login),
        }


class Users(BaseModel):
    """
    Model representing a list of users.
    """

    users: List[User]
