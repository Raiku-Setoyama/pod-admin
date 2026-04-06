"""Product attribute service."""

from app.models.product_attribute import ProductAttributeOption
from app.repositories.product_attribute_repository import ProductAttributeRepository
from app.schemas.product_attribute import (
    ProductAttributeOptionCreate,
    ProductAttributeOptionResponse,
    ProductAttributeOptionUpdate,
    ProductAttributeRequirementResponse,
    ProductAttributeRequirementUpdate,
    ProductAttributeSpecResponse,
)
from app.utils.exceptions import NotFoundError, ValidationError


class ProductAttributeService:
    """Service for product attribute operations."""

    def __init__(self, repo: ProductAttributeRepository):
        self._repo = repo

    async def validate_attributes(
        self,
        product_type: str,
        size: str | None,
        color: str | None,
        position: str | None,
        context: str = "",
    ) -> None:
        """Validate product attributes against DB-registered options.

        Args:
            product_type: The product type to validate against.
            size: Size value to validate (or None).
            color: Color value to validate (or None).
            position: Position value to validate (or None).
            context: Optional context string for error messages (e.g., "uid: abc123").
        """
        requirement = await self._repo.find_requirement(product_type)
        if not requirement:
            raise ValidationError(
                f"No attribute requirements found for product_type '{product_type}'"
            )

        suffix = f" ({context})" if context else ""

        # Fetch all active options for this product_type in a single query
        all_options = await self._repo.find_options(
            product_type=product_type, is_active=True
        )
        options_by_name: dict[str, list[str]] = {}
        for opt in all_options:
            options_by_name.setdefault(opt.attribute_name, []).append(
                opt.attribute_value
            )

        for attr_name, attr_value, is_required in [
            ("size", size, requirement.required_size),
            ("color", color, requirement.required_color),
            ("position", position, requirement.required_position),
        ]:
            if is_required and not attr_value:
                raise ValidationError(
                    f"{attr_name} is required for {product_type}{suffix}"
                )
            if attr_value:
                valid_values = options_by_name.get(attr_name, [])
                if attr_value not in valid_values:
                    raise ValidationError(
                        f"Invalid {attr_name} '{attr_value}'. "
                        f"Valid: {valid_values}{suffix}"
                    )

    async def get_attribute_spec(
        self, product_type: str
    ) -> ProductAttributeSpecResponse:
        """Get combined attribute spec (options + requirements) for a product type."""
        requirement = await self._repo.find_requirement(product_type)
        if not requirement:
            raise NotFoundError("ProductAttributeRequirement", product_type)

        options = await self._repo.find_options(
            product_type=product_type, is_active=True
        )

        sizes = [o.attribute_value for o in options if o.attribute_name == "size"]
        colors = [o.attribute_value for o in options if o.attribute_name == "color"]
        positions = [o.attribute_value for o in options if o.attribute_name == "position"]

        return ProductAttributeSpecResponse(
            product_type=product_type,
            sizes=sizes,
            colors=colors,
            positions=positions,
            required_size=requirement.required_size,
            required_color=requirement.required_color,
            required_position=requirement.required_position,
        )

    # --- CRUD for options ---

    async def list_options(
        self,
        product_type: str,
        attribute_name: str | None = None,
        is_active: bool | None = None,
    ) -> list[ProductAttributeOptionResponse]:
        """List attribute options with optional filters."""
        options = await self._repo.find_options(
            product_type=product_type,
            attribute_name=attribute_name,
            is_active=is_active,
        )
        return [ProductAttributeOptionResponse.model_validate(o) for o in options]

    async def create_option(
        self, data: ProductAttributeOptionCreate
    ) -> ProductAttributeOptionResponse:
        """Create a new attribute option."""
        existing = await self._repo.find_option_by_value(
            product_type=data.product_type,
            attribute_name=data.attribute_name,
            attribute_value=data.attribute_value,
        )
        if existing:
            raise ValidationError(
                f"Attribute option '{data.attribute_value}' already exists "
                f"for {data.product_type}/{data.attribute_name}"
            )

        option = ProductAttributeOption(
            product_type=data.product_type,
            attribute_name=data.attribute_name,
            attribute_value=data.attribute_value,
            display_order=data.display_order,
        )
        option = await self._repo.create_option(option)
        return ProductAttributeOptionResponse.model_validate(option)

    async def update_option(
        self, option_id: str, data: ProductAttributeOptionUpdate
    ) -> ProductAttributeOptionResponse:
        """Update an attribute option."""
        option = await self._repo.find_option_by_id(option_id)
        if not option:
            raise NotFoundError("ProductAttributeOption", option_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(option, field, value)

        option = await self._repo.update_option(option)
        return ProductAttributeOptionResponse.model_validate(option)

    async def delete_option(self, option_id: str) -> None:
        """Delete an attribute option."""
        option = await self._repo.find_option_by_id(option_id)
        if not option:
            raise NotFoundError("ProductAttributeOption", option_id)
        await self._repo.delete_option(option)

    # --- Requirements ---

    async def get_requirement(
        self, product_type: str
    ) -> ProductAttributeRequirementResponse:
        """Get attribute requirements for a product type."""
        requirement = await self._repo.find_requirement(product_type)
        if not requirement:
            raise NotFoundError("ProductAttributeRequirement", product_type)
        return ProductAttributeRequirementResponse.model_validate(requirement)

    async def update_requirement(
        self, product_type: str, data: ProductAttributeRequirementUpdate
    ) -> ProductAttributeRequirementResponse:
        """Update attribute requirements for a product type."""
        requirement = await self._repo.find_requirement(product_type)
        if not requirement:
            raise NotFoundError("ProductAttributeRequirement", product_type)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(requirement, field, value)

        requirement = await self._repo.upsert_requirement(requirement)
        return ProductAttributeRequirementResponse.model_validate(requirement)
