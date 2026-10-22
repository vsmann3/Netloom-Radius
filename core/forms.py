from django import forms
from django.utils import timezone

from .models import NAS, Plan, Subscriber


class NASForm(forms.ModelForm):
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


class PlanForm(forms.ModelForm):
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


class SubscriberForm(forms.ModelForm):
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
