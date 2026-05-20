# Building CRUD Flows Without Mixins

While `reflex-django` provides declarative, high-productivity CRUD classes (like `ModelState` and `ModelCRUDView`) to automate data binding, you may often want **explicit, manual control** over your database transactions. 

Building CRUD flows using plain `AppState` and custom asynchronous ORM calls provides ultimate architectural freedom. It is perfect for complex pages with multi-step workflows, non-standard business logic, or highly customized data validation structures.

This guide is a step-by-step masterclass on how to build a complete, user-scoped product catalog system with manual lists, pagination, text search, creation, editing, and secure deletion.

---

## 1. Under the Hood: The Architecture

When building manual CRUD workflows, you are combining three core pillars:

1. **`AppState`**: Automatically captures cookies and WebSocket headers to establish a thread-safe request context on every user event, exposing **`self.request.user`** (the logged-in user model).
2. **Django Async ORM**: Asynchronously queries and mutates database tables without stalling the event loop.
3. **`ReflexDjangoModelSerializer`**: Dynamically translates rich database rows into flat, JSON-safe dictionaries for reactive binding.

```text
  Client Browser UI                   Reflex Event Handler
 +───────────────────+               +──────────────────────────────────+
 |                   |               | 1. Authenticate with self.user   |
 |  Triggers Event  ─┼──────────────►| 2. Run non-blocking Async Query  |
 |                   |               | 3. Serialize rows with .adata()  |
 |                   |               | 4. Update state variables        |
 |  Renders Changes ◄┼───────────────┼──────────────────────────────────┘
 +───────────────────+
```

---

## 2. Step 1: Declaring the Model and Serializer

For our inventory manager, we will create a `Product` model scoped to a Django user, and its corresponding serializer:

```python
# inventory/models.py
from django.conf import settings
from django.db import models
from reflex_django.model import Model

class Product(Model):
    """An inventory product mapped to a specific authenticated owner."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_products"
    )
    name = models.CharField(max_length=128)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"
```

```python
# inventory/serializers.py
from reflex_django.serializers import ReflexDjangoModelSerializer
from inventory.models import Product

class ProductSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "sku", "price", "category", "is_active", "created_at")
        read_only_fields = ("id", "created_at")
```

Generate and apply the database tables:
```bash
uv run reflex django makemigrations inventory
uv run reflex django migrate
```

---

## 3. Step 2: Defining the State Layout

Subclass **`AppState`** to manage database states. Declare list containers, input bindings for the product form, and control variables for search and pagination:

```python
# frontend/states/inventory.py
import reflex as rx
from django.db.models import Q
from reflex_django.state import AppState
from inventory.models import Product
from inventory.serializers import ProductSerializer

class InventoryState(AppState):
    # Reactive state variables
    products: list[dict] = []
    error_message: str = ""
    
    # Form input field bindings
    name: str = ""
    sku: str = ""
    price: str = ""
    category: str = ""
    is_active: bool = True
    
    # Track which record is currently being edited (-1 means creating a new record)
    editing_id: int = -1
    
    # Search and pagination variables
    search_query: str = ""
    page: int = 1
    page_size: int = 8
    total_pages: int = 1
```

---

## 4. Step 3: Implementing Search, Filters, and List Loading

To protect data privacy, **never** allow a user to load or alter records belonging to others. We write a private helper method `_filtered_qs()` that scopes all database operations to `self.request.user` and applies search parameters:

```python
    def _filtered_qs(self):
        """Builds a database query scoped securely to the active user."""
        # 1. Enforce active authentication
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionError("Authentication required.")
            
        # 2. Scope the queryset
        qs = Product.objects.filter(owner=user)
        
        # 3. Apply search filters
        query = self.search_query.strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query) | 
                Q(sku__icontains=query) |
                Q(category__icontains=query)
            )
            
        return qs.order_by("-created_at")

    @rx.event
    async def load_inventory(self):
        """Asynchronously queries the database, paginates, and serializes the list."""
        self.error_message = ""
        try:
            # Generate the secured base query
            qs = self._filtered_qs()
            
            # Calculate total page count asynchronously
            total_records = await qs.acount()
            self.total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
            
            # Clamp current page boundaries
            self.page = min(self.page, self.total_pages)
            
            # Apply database slicing (LIMIT/OFFSET)
            start = (self.page - 1) * self.page_size
            end = start + self.page_size
            page_qs = qs[start:end]
            
            # Serialize the sliced database records asynchronously
            self.products = await ProductSerializer(page_qs, many=True).adata()
            
        except Exception as e:
            self.error_message = f"Failed to load inventory: {str(e)}"
```

To coordinate search entries and page navigations, add simple state event handlers:

```python
    @rx.event
    def set_search(self, value: str):
        self.search_query = value
        self.page = 1  # Reset to page 1 on search input change

    @rx.event
    async def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
            await self.load_inventory()

    @rx.event
    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
            await self.load_inventory()
```

---

## 5. Step 4: Creating and Updating Records (Upsert)

To handle record creation and updates safely in a single handler, we perform data validation and scope the record lookup using `self.request.user` to prevent Insecure Direct Object Reference (IDOR) attacks:

```python
    def _validate_form(self) -> str | None:
        """Validates form fields on the server before database ingestion."""
        if not self.name.strip():
            return "Product name is required."
        if not self.sku.strip():
            return "SKU code is required."
        try:
            price = float(self.price)
            if price <= 0:
                return "Price must be a positive number."
        except ValueError:
            return "Please enter a valid price."
        return None

    @rx.event
    async def save_product(self):
        """Creates a new product or updates an existing owned product."""
        self.error_message = ""
        
        # 1. Check user authentication
        user = self.request.user
        if not user.is_authenticated:
            return rx.toast.error("Please sign in to save products.")
            
        # 2. Perform validations
        validation_error = self._validate_form()
        if validation_error:
            self.error_message = validation_error
            return
            
        form_data = {
            "name": self.name.strip(),
            "sku": self.sku.strip().upper(),
            "price": self.price,
            "category": self.category.strip(),
            "is_active": self.is_active,
        }
        
        try:
            if self.editing_id >= 0:
                # UPDATE PATH: Securely fetch the object scoped by owner
                product = await Product.objects.aget(pk=self.editing_id, owner=user)
                for key, val in form_data.items():
                    setattr(product, key, val)
                await product.asave()
                rx.toast.success(f"Product '{product.name}' updated successfully.")
            else:
                # CREATE PATH: Assign the logged-in user as the record owner
                new_product = await Product.objects.acreate(owner=user, **form_data)
                rx.toast.success(f"Product '{new_product.name}' added successfully.")
                
            self.reset_form()
            await self.load_inventory()
            
        except Exception as e:
            self.error_message = f"Save failed: {str(e)}"

    @rx.event
    def reset_form(self):
        """Clears form fields and returns state out of editing mode."""
        self.name = ""
        self.sku = ""
        self.price = ""
        self.category = ""
        self.is_active = True
        self.editing_id = -1
        self.error_message = ""
```

---

## 6. Step 5: Editing and Deleting Records

When a user clicks "Edit", we fetch the database row, serialize it, and populate the active state fields. When they click "Delete", we verify ownership before executing the delete command:

```python
    @rx.event
    async def start_editing(self, product_id: int):
        """Loads a product's fields into form inputs for editing."""
        user = self.request.user
        try:
            # Securely retrieve the record
            product = await Product.objects.aget(pk=product_id, owner=user)
            
            # Populate form inputs from the serialized model record
            self.editing_id = product.id
            self.name = product.name
            self.sku = product.sku
            self.price = str(product.price)
            self.category = product.category
            self.is_active = product.is_active
            
        except Exception as e:
            return rx.toast.error("Could not fetch product.")

    @rx.event
    async def delete_product(self, product_id: int):
        """Permanently deletes a product, verified by ownership."""
        user = self.request.user
        try:
            # Secure lookup protects against deleting other users' records
            product = await Product.objects.aget(pk=product_id, owner=user)
            product_name = product.name
            
            await product.adelete()
            rx.toast.success(f"Deleted product '{product_name}'.")
            
            # Reload list
            await self.load_inventory()
            
        except Exception as e:
            return rx.toast.error(f"Deletion failed: {str(e)}")
```

---

## 7. Step 6: Constructing the UI Page Component

Map the state properties directly to styled Reflex page components. Bind the initialization trigger to the `on_load` lifecycle hook:

```python
# frontend/pages/inventory.py
import reflex as rx
from frontend.states.inventory import InventoryState

def inventory_view() -> rx.Component:
    return rx.container(
        rx.heading("My Private Inventory", size="8", margin_bottom="1.5rem"),
        
        # Display validation/server errors
        rx.cond(
            InventoryState.error_message != "",
            rx.callout(InventoryState.error_message, color_scheme="red", margin_bottom="1.5rem")
        ),
        
        rx.grid(
            # LEFT SIDE: Product upsert form
            rx.card(
                rx.vstack(
                    rx.heading(
                        rx.cond(InventoryState.editing_id >= 0, "Edit Product", "Add New Product"),
                        size="4"
                    ),
                    rx.input(placeholder="Product Name", value=InventoryState.name, on_change=InventoryState.set_name, width="100%"),
                    rx.input(placeholder="SKU Code", value=InventoryState.sku, on_change=InventoryState.set_sku, width="100%"),
                    rx.input(placeholder="Price ($)", value=InventoryState.price, on_change=InventoryState.set_price, width="100%"),
                    rx.input(placeholder="Category", value=InventoryState.category, on_change=InventoryState.set_category, width="100%"),
                    
                    rx.hstack(
                        rx.text("Product is Active"),
                        rx.switch(checked=InventoryState.is_active, on_change=InventoryState.set_is_active),
                        justify="between", width="100%", padding="0.5rem 0"
                    ),
                    
                    rx.hstack(
                        rx.button("Save Product", on_click=InventoryState.save_product, color_scheme="indigo"),
                        rx.cond(
                            InventoryState.editing_id >= 0,
                            rx.button("Cancel", on_click=InventoryState.reset_form, color_scheme="gray", variant="ghost")
                        ),
                        width="100%"
                    ),
                    spacing="3", width="100%"
                ),
                padding="1.5rem"
            ),
            
            # RIGHT SIDE: Product Catalog Grid & List
            rx.vstack(
                # Search Bar
                rx.hstack(
                    rx.input(
                        placeholder="Search by name, SKU, or category...",
                        value=InventoryState.search_query,
                        on_change=InventoryState.set_search,
                        width="100%"
                    ),
                    rx.button("Search", on_click=InventoryState.load_inventory),
                    width="100%"
                ),
                
                # Product Table/Cards
                rx.vstack(
                    rx.foreach(
                        InventoryState.products,
                        lambda row: rx.hstack(
                            rx.vstack(
                                rx.text(row["name"], weight="bold"),
                                rx.hstack(
                                    rx.badge(row["sku"], color_scheme="gray"),
                                    rx.text(f"${row['price']}", color_scheme="green")
                                ),
                                align_items="start"
                            ),
                            rx.spacer(),
                            rx.hstack(
                                rx.button("Edit", size="2", on_click=InventoryState.start_editing(row["id"]), color_scheme="blue", variant="surface"),
                                rx.button("Delete", size="2", on_click=InventoryState.delete_product(row["id"]), color_scheme="red", variant="ghost")
                            ),
                            width="100%", padding="0.75rem", border_bottom="1px solid rgba(0,0,0,0.08)"
                        )
                    ),
                    width="100%", min_height="300px"
                ),
                
                # Pagination controls
                rx.hstack(
                    rx.button("Previous", on_click=InventoryState.prev_page, disabled=InventoryState.page == 1),
                    rx.text(f"Page {InventoryState.page} of {InventoryState.total_pages}"),
                    rx.button("Next", on_click=InventoryState.next_page, disabled=InventoryState.page == InventoryState.total_pages),
                    justify="between", width="100%", margin_top="1rem"
                ),
                width="100%"
            ),
            columns="2", spacing="6", width="100%"
        ),
        padding="2rem"
    )

# Registration on the app layout
# app.add_page(inventory_view, route="/inventory", on_load=InventoryState.load_inventory)
```

---

## 8. Summary Comparison: Manual vs Declarative CRUD

| Engineering Feature | Manual Flow (This Guide) | Declarative (`ModelCRUDView`) |
|:---|:---|:---|
| **Boilerplate Code** | High (You write every `@rx.event` and form validator). | Extremely Low (All event handlers and fields are generated). |
| **Logic Customization** | Infinite (Complete control over query slicing and updates). | Moderate (Customized by overriding CRUD hooks like `get_queryset`). |
| **IDOR Protection** | Manual (You must verify `owner=user` inside query lookups). | Automatic (Managed via standard mixins like `UserScopedMixin`). |
| **Form Reset Handling** | Manual (You must define clear reset methods). | Automatic (Managed internally by tracking dynamic `form_reset_key`). |

---

**Navigation:** [← Model Serializers](serializers.md) | [Next: ModelState vs ModelCRUDView →](model_state_and_crud_view.md)
