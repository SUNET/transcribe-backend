from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
from sqlalchemy.types import Enum as SQLAlchemyEnum
from sqlmodel import Field
from enum import Enum
from sqlmodel import SQLModel


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
            "status": self.status,
            "job_type": self.job_type,
            "created_at": str(self.created_at),
            "updated_at": str(self.updated_at),
            "language": self.language,
            "model_type": self.model_type,
            "filename": self.filename,
            "output_format": self.output_format,
            "error": self.error,
        }


class Jobs(BaseModel):
    """
    Model representing a list of jobs.
    """

    jobs: List[Job]
