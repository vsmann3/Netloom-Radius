from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import NAS, Plan, Subscriber


class DashboardFormMixin:
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", self.__class__.__name__.lower() + "_%s")
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class SubscriberFilterForm(DashboardFormMixin, forms.Form):
    account_id = forms.UUIDField(required=False, label="Account ID", help_text="Exact subscriber account UUID")
    username = forms.CharField(required=False, max_length=64, label="Username contains")
    status = forms.ChoiceField(required=False, choices=[("", "Any status"), ("active", "Active"), ("suspended", "Suspended")])
    validity = forms.ChoiceField(required=False, choices=[("", "Any expiry"), ("valid", "Not expired"), ("expired", "Expired"), ("expiring", "Expires in next 7 days")])
    plan = forms.ModelChoiceField(queryset=Plan.objects.none(), required=False, empty_label="All plans")
    expiry_from = forms.DateField(required=False, label="Expiry from (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    expiry_to = forms.DateField(required=False, label="Expiry through (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    created_from = forms.DateField(required=False, label="Created from (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    created_to = forms.DateField(required=False, label="Created through (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    renewal_from = forms.DateField(required=False, label="Last renewal from (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    renewal_to = forms.DateField(required=False, label="Last renewal through (UTC)", widget=forms.DateInput(attrs={"type": "date"}))
    renewal_record = forms.ChoiceField(required=False, label="Renewal history", choices=[("", "Any renewal history"), ("recorded", "Has a recorded renewal"), ("unrecorded", "No renewal recorded")])
    sort = forms.ChoiceField(required=False, label="Sort by", choices=[("username", "Username A–Z"), ("-username", "Username Z–A"), ("expires_at", "Expiry: earliest first"), ("-expires_at", "Expiry: latest first"), ("-created_at", "Newest accounts"), ("created_at", "Oldest accounts")])
    per_page = forms.TypedChoiceField(required=False, label="Rows per page", coerce=int, choices=[(25, "25"), (50, "50"), (100, "100")])

    def __init__(self, *args, tenant_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = Plan.objects.filter(tenant_id=tenant_id).order_by("name")

    def clean(self):
        data = super().clean()
        for prefix in ("expiry", "created", "renewal"):
            start, end = data.get(prefix + "_from"), data.get(prefix + "_to")
            for suffix, value in [("_from", start), ("_to", end)]:
                if value and value.year < 1000:
                    self.add_error(prefix + suffix, "Use a year of 1000 or later.")
            if start and end and start > end:
                self.add_error(prefix + "_to", ValidationError("End date must be on or after the start date."))
        return data


class NASForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = NAS
        fields = ["name", "source_ip"]
        labels = {"source_ip": "RADIUS source IPv4 address"}
        help_texts = {"source_ip": "The address FreeRADIUS receives packets from."}

    def validate_unique(self):
        # Do not disclose another company's router registration through validation.
        try:
            self.instance.validate_unique(exclude=self._get_validation_exclusions())
        except forms.ValidationError:
            self.add_error("source_ip", "This address is unavailable for registration.")


class PlanForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Plan
        fields = ["name", "upload_kbps", "download_kbps"]

    def __init__(self, *args, tenant_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tenant_id = tenant_id

    def clean_name(self):
        name = self.cleaned_data["name"]
        if Plan.objects.filter(tenant_id=self.instance.tenant_id, name=name).exists():
            raise forms.ValidationError("A plan with this name already exists.")
        return name


class SubscriberForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ["username", "plan", "expires_at"]
        widgets = {"expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, tenant_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tenant_id = tenant_id
        self.fields["plan"].queryset = Plan.objects.filter(tenant_id=tenant_id).order_by("name")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if Subscriber.objects.filter(tenant_id=self.instance.tenant_id, username__iexact=username).exists():
            raise forms.ValidationError("A subscriber with this username already exists.")
        return username

    def clean_expires_at(self):
        value = self.cleaned_data["expires_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Choose a future expiry date.")
        return value
