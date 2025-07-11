from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Habit, HabitEntry
from .serializers import HabitEntrySerializer, HabitSerializer


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


@extend_schema_view(
    list=extend_schema(
        tags=["Habits"],
        summary="List user's habits",
        description="Get all habits for the authenticated user. Use ?archived=true/false to filter.",
        parameters=[
            OpenApiParameter(
                name="archived",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Filter by archived status",
                required=False,
            ),
        ],
    ),
    create=extend_schema(
        tags=["Habits"],
        summary="Create a new habit",
        description="Create a new habit for the authenticated user.",
    ),
    retrieve=extend_schema(
        tags=["Habits"],
        summary="Get habit details",
        description="Retrieve details of a specific habit.",
    ),
    update=extend_schema(
        tags=["Habits"],
        summary="Update habit",
        description="Update all fields of a habit (PUT).",
    ),
    partial_update=extend_schema(
        tags=["Habits"],
        summary="Partially update habit",
        description="Update specific fields of a habit (PATCH).",
    ),
    destroy=extend_schema(
        tags=["Habits"],
        summary="Delete habit",
        description="Permanently delete a habit (hard delete).",
    ),
)
class HabitViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Habits.

    Allows authenticated users to create, view, update, archive,
    and unarchive their own habits.
    """

    serializer_class = HabitSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):  # type: ignore
        user = self.request.user
        queryset = Habit.objects.filter(user=user)

        if self.action == "list":
            is_archived_param = self.request.query_params.get("archived")  # type: ignore
            if is_archived_param is not None:
                if is_archived_param.lower() in ["true", "1"]:
                    queryset = queryset.filter(archived_at__isnull=False)
                elif is_archived_param.lower() in ["false", "0"]:
                    queryset = queryset.filter(archived_at__isnull=True)
            else:
                queryset = queryset.filter(archived_at__isnull=True)

        return queryset.order_by("name")

    def perform_create(self, serializer):
        """(Internal method called by create action) Associates the habit with the user."""
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()

    def list(self, request, *args, **kwargs):
        """
        List Habits for the authenticated user.

        By default, only lists *active* (non-archived) habits.
        Use query parameter `?archived=true` to list only archived habits.
        Use query parameter `?archived=false` to explicitly list only active habits.
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new Habit for the authenticated user.

        Requires 'name' and 'type' fields. Other fields like 'description',
        'color', 'goal_value', 'goal_unit' are optional.
        The 'user' field is set automatically.
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the details of a specific Habit by its ID.

        Can retrieve both active and archived habits belonging to the user.
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update all fields of a specific Habit by its ID (PUT).

        Requires all fields (except read-only ones) to be provided.
        Use PATCH for partial updates.
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update fields of a specific Habit by its ID (PATCH).

        Only include the fields you want to change in the request body.
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a specific Habit by its ID.

        This performs a hard delete (removes the record from the database).
        Returns a 204 No Content response on success.
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=["Habits"],
        summary="Archive a habit",
        description="Archive a habit (soft delete). Sets archived_at timestamp.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """
        Explicitly archive a specific habit by its ID (Soft Delete).

        Sets the 'archived_at' timestamp to the current time.
        Returns the updated habit data. Idempotent (does nothing if already archived).
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        habit = self.get_object()
        if habit.archived_at is None:
            habit.archived_at = timezone.now()
            habit.save()
        serializer = self.get_serializer(habit)
        return Response(serializer.data)

    @extend_schema(
        tags=["Habits"],
        summary="Unarchive a habit",
        description="Reactivate an archived habit. Clears archived_at timestamp.",
        request=None,
    )
    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        """
        Reactivates (unarchives) a specific archived habit by its ID.

        Sets the 'archived_at' timestamp back to null.
        Returns the updated habit data. Idempotent (does nothing if already active).
        Returns 404 if the habit does not exist or does not belong to the user.
        """
        habit = self.get_object()
        if habit.archived_at is not None:
            habit.archived_at = None
            habit.save()
        serializer = self.get_serializer(habit)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=["Entries"],
        summary="List habit entries",
        description="Get habit entries for the authenticated user with optional filtering.",
        parameters=[
            OpenApiParameter(
                name="habit_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by specific habit ID",
                required=False,
            ),
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter entries from this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter entries until this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description="Filter entries for specific date (YYYY-MM-DD)",
                required=False,
            ),
        ],
    ),
    create=extend_schema(
        tags=["Entries"],
        summary="Create habit entry",
        description="Log a habit completion for a specific date.",
    ),
    retrieve=extend_schema(
        tags=["Entries"],
        summary="Get entry details",
        description="Retrieve details of a specific habit entry.",
    ),
    update=extend_schema(
        tags=["Entries"],
        summary="Update entry",
        description="Update all fields of a habit entry (PUT).",
    ),
    partial_update=extend_schema(
        tags=["Entries"],
        summary="Partially update entry",
        description="Update specific fields of a habit entry (PATCH).",
    ),
    destroy=extend_schema(
        tags=["Entries"],
        summary="Delete entry",
        description="Permanently delete a habit entry.",
    ),
)
class HabitEntryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Habit Entries (logs of habit completion).

    Allows authenticated users to log completions (entries) for their habits,
    view their history, and update/delete specific entries. Entries represent
    a habit performed on a specific date with an associated value (e.g., 1 for
    singular habits, duration for timed habits).
    """

    serializer_class = HabitEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):  # type: ignore
        """
        Dynamically filters the queryset based on query parameters.

        - Restricts entries to the authenticated user.
        - Filters by `habit_id` if provided.
        - Filters by date range (`start_date`, `end_date`) if provided.
        - Filters by specific `date` if provided.
        """
        user = self.request.user
        queryset = HabitEntry.objects.filter(user=user)

        habit_id = self.request.query_params.get("habit_id")  # type: ignore
        if habit_id:
            try:
                queryset = queryset.filter(habit__id=int(habit_id))
            except (ValueError, TypeError):
                pass

        start_date = self.request.query_params.get("start_date")  # type: ignore
        end_date = self.request.query_params.get("end_date")  # type: ignore

        if start_date:
            queryset = queryset.filter(entry_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(entry_date__lte=end_date)

        specific_date = self.request.query_params.get("date")  # type: ignore
        if specific_date:
            queryset = queryset.filter(entry_date=specific_date)

        return queryset.order_by("-entry_date")

    def get_serializer_context(self):
        """Pass request context to the serializer for validation."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):
        """
        List Habit Entries for the authenticated user.

        Supports filtering via query parameters:
        - `habit_id=<id>`: Filter by a specific habit.
        - `start_date=YYYY-MM-DD`: Filter by entries on or after this date.
        - `end_date=YYYY-MM-DD`: Filter by entries on or before this date.
        - `date=YYYY-MM-DD`: Filter by entries on a specific date.
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new Habit Entry (log a habit completion).

        Requires:
        - `habit`: The ID of the habit being logged.
        - `entry_date`: The date (YYYY-MM-DD) the habit was performed.
        - `value`: The value associated with the entry (1 for singular, duration for timed).

        Optional:
        - `notes`: User notes for this entry.

        The 'user' field is set automatically. Fails if the habit is archived,
        doesn't belong to the user, or if an entry for the same habit/date exists.
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve the details of a specific Habit Entry by its ID.

        Returns 404 if the entry does not exist or does not belong to the user.
        """
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update all fields of a specific Habit Entry by its ID (PUT).

        Requires all fields (except read-only ones) to be provided.
        Use PATCH for partial updates.
        Returns 404 if the entry does not exist or does not belong to the user.
        Fails if the new value is invalid for the habit type.
        """
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        Partially update fields of a specific Habit Entry by its ID (PATCH).

        Only include the fields you want to change (e.g., `value`, `notes`).
        Returns 404 if the entry does not exist or does not belong to the user.
        Fails if the new value is invalid for the habit type.
        """
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a specific Habit Entry by its ID.

        This performs a hard delete (removes the record from the database).
        Returns a 204 No Content response on success.
        Returns 404 if the entry does not exist or does not belong to the user.
        """
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        """(Internal) Extra checks before serializer saves the entry."""
        serializer.save()
