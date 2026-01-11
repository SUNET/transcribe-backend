import re

from db.models import AttributeConditionEnum, AttributeRules
from db.session import get_session
from db.user import user_update
from typing import Optional


def rule_add(
    name: str,
    attribute_name: str,
    attribute_condition: AttributeConditionEnum,
    attribute_value: str,
    activate: Optional[bool] = None,
    admin: Optional[bool] = None,
    assign_to_group: Optional[str] = None,
    assign_to_admin_domains: Optional[str] = None,
    realm_filter: Optional[str] = None,
    owner_domains: Optional[str] = None,
) -> AttributeRules:
    """
    Set default values for optional attributes in AttributeRules.

    Parameters:
            rules (AttributeRules): The AttributeRules object to set defaults for.

    Returns:
            AttributeRules: The updated AttributeRules object with defaults set.
    """

    with get_session() as session:
        rule = AttributeRules(
            name=name,
            attribute_name=attribute_name,
            attribute_condition=attribute_condition,
            attribute_value=attribute_value,
            activate=activate if activate is not None else True,
            admin=admin if admin is not None else False,
            assign_to_group=assign_to_group if assign_to_group is not None else "",
            assign_to_admin_domains=assign_to_admin_domains
            if assign_to_admin_domains is not None
            else "",
            realm_filter=realm_filter if realm_filter is not None else "",
            owner_domains=owner_domains if owner_domains is not None else "",
        )

        session.add(rule)

        return rule.as_dict()


def rule_update(
    rule_id: int,
    name: Optional[str] = None,
    attribute_name: Optional[str] = None,
    attribute_condition: Optional[AttributeConditionEnum] = None,
    attribute_value: Optional[str] = None,
    activate: Optional[bool] = None,
    admin: Optional[bool] = None,
    assign_to_group: Optional[str] = None,
    assign_to_admin_domains: Optional[str] = None,
    realm_filter: Optional[str] = None,
    owner_domains: Optional[str] = None,
) -> Optional[AttributeRules]:
    """
    Update an existing attribute rule by its ID.

    Parameters:
        rule_id (int): The ID of the rule to update.
        name (Optional[str]): The new name for the rule.
        attribute_name (Optional[str]): The new attribute name.
        attribute_condition (Optional[AttributeConditionEnum]): The new attribute condition.
        attribute_value (Optional[str]): The new attribute value.
        activate (Optional[bool]): The new activation status.
        admin (Optional[bool]): The new admin status.
        assign_to_group (Optional[str]): The new group assignment.
        assign_to_admin_domains (Optional[str]): The new admin domains assignment.
        realm_filter (Optional[str]): The new realm filter.
        owner_domains (Optional[str]): The new owner domains.

    Returns:
        Optional[AttributeRules]: The updated AttributeRules object, or None if not found.
    """

    with get_session() as session:
        rule = (
            session.query(AttributeRules).filter(AttributeRules.id == rule_id).first()
        )

        if not rule:
            return None

        if name is not None:
            rule.name = name
        if attribute_name is not None:
            rule.attribute_name = attribute_name
        if attribute_condition is not None:
            rule.attribute_condition = attribute_condition
        if attribute_value is not None:
            rule.attribute_value = attribute_value
        if activate is not None:
            rule.activate = activate
        if admin is not None:
            rule.admin = admin
        if assign_to_group is not None:
            rule.assign_to_group = assign_to_group
        if assign_to_admin_domains is not None:
            rule.assign_to_admin_domains = assign_to_admin_domains
        if realm_filter is not None:
            rule.realm_filter = realm_filter
        if owner_domains is not None:
            rule.owner_domains = owner_domains

        return rule.as_dict()


def rule_delete(rule_id: int) -> bool:
    """
    Delete an attribute rule by its ID.

    Parameters:
        rule_id (int): The ID of the rule to delete.

    Returns:
        bool: True if the rule was deleted, False otherwise.
    """

    with get_session() as session:
        rule = (
            session.query(AttributeRules).filter(AttributeRules.id == rule_id).first()
        )

        if not rule:
            return False

        session.delete(rule)
        return True


def rules_get_all() -> list[AttributeRules]:
    """
    Retrieve all attribute rules from the database.

    Returns:
        list[AttributeRules]: A list of all AttributeRules objects.
    """

    with get_session() as session:
        rules = session.query(AttributeRules).all()

        if not rules:
            return []

        return [rule.as_dict() for rule in rules]


def rules_match_user(user_attributes: dict) -> list[AttributeRules]:
    """
    Retrieve all attribute rules that match the given user attributes.

    Parameters:
        user_attributes (dict[str, str]): A dictionary of user attributes.

    Returns:
        list[AttributeRules]: A list of matching AttributeRules objects.
    """

    accept = False

    with get_session() as session:
        rules = session.query(AttributeRules).all()

        for rule in rules:
            if not (attribute_name := user_attributes.get(rule.attribute_name)):
                continue

            match rule.attribute_condition:
                case AttributeConditionEnum.EQUALS:
                    if attribute_name == rule.attribute_value:
                        accept = True
                case AttributeConditionEnum.NOT_EQUALS:
                    if attribute_name != rule.attribute_value:
                        accept = True
                case AttributeConditionEnum.CONTAINS:
                    if rule.attribute_value in attribute_name:
                        accept = True
                case AttributeConditionEnum.NOT_CONTAINS:
                    if rule.attribute_value not in attribute_name:
                        accept = True
                case AttributeConditionEnum.STARTS_WITH:
                    if attribute_name.startswith(rule.attribute_value):
                        accept = True
                case AttributeConditionEnum.ENDS_WITH:
                    if attribute_name.endswith(rule.attribute_value):
                        accept = True
                case AttributeConditionEnum.REGEX:
                    if re.match(rule.attribute_value, attribute_name):
                        accept = True

            if rule.owner_domains:
                owner_domains = rule.owner_domains.split(",")
                if not any(domain in attribute_name for domain in owner_domains):
                    accept = False

            if rule.realm_filter:
                realm_filters = rule.realm_filter.split(",")
                if not any(domain in attribute_name for domain in realm_filters):
                    accept = False

            if accept and rule.admin:
                user_update(user_attributes["sub"], admin=True)

            if accept and rule.activate:
                user_update(user_attributes["sub"], active=True)

            if accept and rule.assign_to_group:
                pass

        return accept
