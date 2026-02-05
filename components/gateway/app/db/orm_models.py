from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .session import Base


# -------------------------
# Association / join tables
# -------------------------

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

mcp_servers_user_access = Table(
    "mcp_servers_user_access",
    Base.metadata,
    Column("server_id", Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

mcp_servers_role_access = Table(
    "mcp_servers_role_access",
    Base.metadata,
    Column("server_id", Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

corpus_user_access = Table(
    "corpus_user_access",
    Base.metadata,
    Column("corpus_id", Text, ForeignKey("corpora.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

corpus_role_access = Table(
    "corpus_role_access",
    Base.metadata,
    Column("corpus_id", Text, ForeignKey("corpora.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# --------
# Entities
# --------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # many-to-many: users <-> roles
    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    # many-to-many: users <-> mcp_servers (access)
    mcp_servers: Mapped[list["MCPServer"]] = relationship(
        secondary=mcp_servers_user_access,
        back_populates="users_with_access",
        lazy="selectin",
    )

    # many-to-many: users <-> corpora (access)
    corpora: Mapped[list["Corpus"]] = relationship(
        secondary=corpus_user_access,
        back_populates="users_with_access",
        lazy="selectin",
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # many-to-many: roles <-> users
    users: Mapped[list["User"]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )

    # many-to-many: roles <-> mcp_servers (access)
    mcp_servers: Mapped[list["MCPServer"]] = relationship(
        secondary=mcp_servers_role_access,
        back_populates="roles_with_access",
        lazy="selectin",
    )

    # many-to-many: roles <-> corpora (access)
    corpora: Mapped[list["Corpus"]] = relationship(
        secondary=corpus_role_access,
        back_populates="roles_with_access",
        lazy="selectin",
    )


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # JSONB NOT NULL DEFAULT '{}'
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # access by user
    users_with_access: Mapped[list["User"]] = relationship(
        secondary=mcp_servers_user_access,
        back_populates="mcp_servers",
        lazy="selectin",
    )

    # access by role
    roles_with_access: Mapped[list["Role"]] = relationship(
        secondary=mcp_servers_role_access,
        back_populates="mcp_servers",
        lazy="selectin",
    )


class Corpus(Base):
    __tablename__ = "corpora"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # TEXT PK TODO is the same as 'name'. check dependencies and remove one...
    name: Mapped[str] = mapped_column(Text, nullable=False)
    database_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # access by user
    users_with_access: Mapped[list["User"]] = relationship(
        secondary=corpus_user_access,
        back_populates="corpora",
        lazy="selectin",
    )

    # access by role
    roles_with_access: Mapped[list["Role"]] = relationship(
        secondary=corpus_role_access,
        back_populates="corpora",
        lazy="selectin",
    )
