from abc import ABC, abstractmethod
from typing import Dict, List, ClassVar, Optional, Type, Set, Any

from attr import define, field

from resotocore.ids import ConfigId, Email, Password
from resotocore.model.typed_model import to_js
from resotocore.types import Json
from resotocore.service import Service
from resotolib.core.model_export import dataclasses_to_resotocore_model

UsersConfigRoot = "resoto_users"
UsersConfigId = ConfigId("resoto.users")


@define
class ResotoUser:
    kind: ClassVar[str] = "resoto_user"
    fullname: str = field(metadata={"description": "The full name of the user."})
    password_hash: str = field(metadata={"description": "The sha256 hash of the user's password."})
    roles: Set[str] = field(factory=set, metadata={"description": "The roles of the user."})


@define
class ResotoUsersConfig:
    kind: ClassVar[str] = UsersConfigRoot
    users: Dict[str, ResotoUser] = field(factory=lambda: {}, metadata={"description": "A map of email to user data."})

    def json(self) -> Json:
        return {UsersConfigRoot: to_js(self, strip_attr="kind")}


class UserManagement(Service, ABC):
    @abstractmethod
    async def has_users(self) -> bool:
        """
        Indicates if users exist in the system.
        """

    @abstractmethod
    async def create_first_user(self, company: str, fullname: str, email: Email, password: Password) -> ResotoUser:
        """
        Create the first user in the system.
        Precondition: has_users() == False
        :param company: the name of the company
        :param fullname: the full name of the user
        :param email: the email address of the user
        :param password: the password of the user
        :return: the created user
        :throws: AssertionError if there are already users in the system.
        """

    @abstractmethod
    async def login(self, email: Email, password: Password) -> Optional[ResotoUser]:
        """
        Login with the given credentials.
        :param email: the email address of the user
        :param password: the password of the user
        :return: The user if the credentials are valid, None otherwise.
        """

    @abstractmethod
    async def create_user(self, email: Email, fullname: str, password: Password, roles: List[str]) -> ResotoUser:
        """
        Create a new user.
        :param email: the email address of the user
        :param fullname: the full name of the user
        :param password: password of the user
        :param roles: all roles of the user
        :return: the created user
        """

    @abstractmethod
    async def update_user(
        self, email: Email, *, password: Optional[Password] = None, roles: Optional[List[str]] = None
    ) -> ResotoUser:
        """
        Update an existing user.

        :param email: the email address of the user
        :param password: the new password of the user
        :param roles: all roles of the user
        :return: the updated user
        """

    @abstractmethod
    async def delete_user(self, email: Email) -> Optional[ResotoUser]:
        """
        Delete an existing user.
        :param email: the email address of the user
        :return: the deleted user if it existed before calling this method, None otherwise
        """

    @abstractmethod
    async def user(self, email: Email) -> Optional[ResotoUser]:
        """
        Get a user by email.
        :param email: the email address of the user
        :return: the user if it exists, None otherwise
        """

    @abstractmethod
    async def users(self) -> Dict[Email, ResotoUser]:
        """
        List all users.
        :return: the list of users.
        """


def config_model() -> List[Json]:
    config_classes: Set[Type[Any]] = {ResotoUsersConfig}
    return dataclasses_to_resotocore_model(config_classes, use_optional_as_required=True)
