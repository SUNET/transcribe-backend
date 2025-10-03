from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
from sqlalchemy.types import Enum as SQLAlchemyEnum
from sqlmodel import Field, Relationship, SQLModel
from typing import List, Optional
from uuid import uuid4


# +-------------------+             +---------------------+             +--------------------------+
# |       User        |             |   GroupUserLink     |             |       Group              |
# |-------------------|             |---------------------|             |--------------------------|
# | id (PK)           |<----------->| user_id (FK ->User) |             | id (PK)                  |
# | user_id           |             | group_id (FK->Group)|<----------->| name                     |
# | username          |             | role                |             | description              |
# | realm             |             +---------------------+             | created_at               |
# | admin (bool)      |                                                 | owner_user_id (FK->User) |
# | bofh  (bool)      |                                                 | quota_seconds            |
# | transcribed_secs  |                                                 +---------+----------------+
# | last_login        |                                                             |
# | active (bool)     |                                                             |
# +---------+---------+                                                             |
#           ^                                                                       |
#           |                                                                       |
#           |                                                                       v
#           |                                                           +-------------------+
#           |                                                           |  GroupModelLink   |
#           |                                                           |-------------------|
#           |                                                           | group_id (FK->Grp)|
#           |                                                           | model_id (FK->Mod)|
#           |                                                           +---------+---------+
#           |                                                                     |
#           |                                                                     |
# +---------+---------+                                                           v
# |   JobResult       |                                                 +-------------------+
# |-------------------|                                                 |      Model        |
# | id (PK)           |                                                 |-------------------|
# | job_id (UUID)     |                                                 | id (PK)           |
# | user_id           |                                                 | name (unique)     |
# | result (JSON)     |                                                 | description       |
# | result_srt        |                                                 | active (bool)     |
# | created_at        |                                                 +-------------------+
# +-------------------+
#           ^
#           |
#           |
# +---------+---------+
# |       Job         |
# |-------------------|
# | id (PK)           |
# | uuid (UUID)       |
# | user_id           |
# | status (Enum)     |
# | job_type (Enum)   |
# | created_at        |
# | updated_at        |
# | deletion_date     |
# | language          |
# | model_type        |
# | speakers          |
# | error             |
# | filename          |
# | output_format     |
# | transcribed_secs  |
# +-------------------+


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
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
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
    deletion_date: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=7),
        description="Date when the job will be deleted",
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
    transcribed_seconds: int = Field(default=0, description="Transcribed seconds")

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
            "deletion_date": str(self.deletion_date),
            "language": self.language,
            "model_type": self.model_type,
            "filename": self.filename,
            "speakers": self.speakers,
            "output_format": self.output_format,
            "error": self.error,
            "transcribed_seconds": self.transcribed_seconds,
        }


class Jobs(BaseModel):
    """
    Model representing a list of jobs.
    """

    jobs: List[Job]


class GroupUserLink(SQLModel, table=True):
    """
    Link table between groups and users.
    Defines which users belong to which groups.
    """

    __tablename__ = "group_user_link"

    group_id: Optional[int] = Field(
        default=None, foreign_key="groups.id", primary_key=True
    )
    user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", primary_key=True
    )
    role: str = Field(default="member", description="Role of the user in the group")
    in_group: bool = Field(
        default=True, description="Indicates if the user is currently in the group"
    )


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
    bofh: bool = Field(
        default=False,
        description="Indicates if the user is a BOFH",
    )
    transcribed_seconds: int = Field(
        default=None,
        description="Transcribed seconds",
    )
    last_login: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last login timestamp",
    )
    active: bool = Field(
        default=False,
        description="Indicates if the user is active",
    )
    groups: List["Group"] = Relationship(
        back_populates="users", link_model=GroupUserLink
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
            "active": self.active,
            "bofh": self.bofh,
        }


class Users(BaseModel):
    """
    Model representing a list of users.
    """

    users: List[User]


# Block diagram of the connection between users, groups, quota, models etc
#
# User <--> GroupUserLink <--> Group <--> GroupModelLink <--> Model
#  ^                                                        ^
#  |                                                        |
#  +----------------- transcribed_seconds ------------------+
#                                                           |
#                           quota_seconds ------------------+
#                           active (Model)                  |
#                           admin (User)                    |
#                           bofh (User)                     |
#                                                           +------------------ owner_user_id (Group)
#
# -----------------------------------------------------------
# This design allows for:
# - Users to belong to multiple groups
# - Groups to have access to multiple models
# - Each group can have a monthly quota in seconds
# - Each user has a total of transcribed seconds
# - Admin users can manage groups and users
# - BOFH users can view statistics across all realms
# - Each group has an owner or primary contact user
# -----------------------------------------------------------


class GroupModelLink(SQLModel, table=True):
    """
    Link table between groups and models.
    Defines which models a group has access to.
    """

    __tablename__ = "group_model_link"

    group_id: int = Field(foreign_key="groups.id", primary_key=True)
    model_id: int = Field(foreign_key="models.id", primary_key=True)


class Model(SQLModel, table=True):
    """
    Model representing a transcription model type.
    """

    __tablename__ = "models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(
        index=True, unique=True, description="Model name (e.g., base, large)"
    )
    description: str = Field(default=None, description="Model description")
    active: bool = Field(
        default=True, description="Whether the model is currently available"
    )

    groups: List["Group"] = Relationship(
        back_populates="allowed_models", link_model=GroupModelLink
    )


class Group(SQLModel, table=True):
    """
    Model representing a user group.
    """

    __tablename__ = "groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    realm: str = Field(index=True, description="Realm the group belongs to")
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Group management
    owner_user_id: Optional[int] = Field(
        foreign_key="users.id", description="Owner or primary contact for this group"
    )
    quota_seconds: Optional[int] = Field(
        default=None, description="Monthly quota in seconds"
    )

    # Relationships
    users: List["User"] = Relationship(
        back_populates="groups", link_model=GroupUserLink
    )
    allowed_models: List["Model"] = Relationship(
        back_populates="groups", link_model=GroupModelLink
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "realm": self.realm,
            "description": self.description,
            "created_at": str(self.created_at),
            "owner_user_id": self.owner_user_id,
            "quota_seconds": self.quota_seconds,
            "user_count": len(self.users),
            "transcribed_seconds_total": sum(
                u.transcribed_seconds or 0 for u in self.users
            ),
            "allowed_models": [m.name for m in self.allowed_models],
            "users": [u.as_dict() for u in self.users] if self.users else [],
        }
