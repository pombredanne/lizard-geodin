from __future__ import unicode_literals
import logging

from django.contrib import messages
from django.contrib.gis import admin
from django.utils.translation import ugettext as _

from lizard_geodin import models

logger = logging.getLogger(__name__)


class ApiStartingPointAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name', 'source_url')
    actions = ['reload']
    prepopulated_fields = {"slug": ("name",)}

    def reload(self, request, queryset):
        num_updated = 0
        for api_starting_point in queryset:
            try:
                api_starting_point.load_from_geodin()
                num_updated += 1
            except Exception, e:
                msg = ("Something went wrong when updating %s. " +
                       "Look at %s directly. The error: %s")
                msg = msg % (api_starting_point.name,
                             api_starting_point.source_url,
                             e)
                logger.exception(msg)
                messages.error(request, msg)
        self.message_user(
            request,
            "Reloaded %s api starting points." % (num_updated))

    reload.short_description = _(
        "Reload list of available projects from API")


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('slug', 'active', 'name', 'source_url')
    list_editable = ('active', )
    actions = ['reload']

    def reload(self, request, queryset):
        num_updated = 0
        for project in queryset:
            try:
                project.load_from_geodin()
                num_updated += 1
            except Exception, e:
                msg = ("Something went wrong when updating %s. " +
                       "Look at %s directly. The error: %s")
                msg = msg % (project.name,
                             project.source_url,
                             e)
                logger.exception(msg)
                messages.error(request, msg)
        self.message_user(
            request,
            "Reloaded %s projects." % (num_updated))

    reload.short_description = _("Update project from API")


class MeasurementAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project', 'supplier', 'parameter')


class PointAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'slug', 'name', 'measurement')
    list_filter = ('measurement__project', 'measurement__supplier',)


class SupplierAdmin(admin.GeoModelAdmin):
    list_display = ('slug', 'name', 'html_color')
    list_editable = ('html_color', )


admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.Measurement, MeasurementAdmin)
admin.site.register(models.ApiStartingPoint, ApiStartingPointAdmin)
admin.site.register(models.Point, PointAdmin)
admin.site.register(models.Supplier, SupplierAdmin)
admin.site.register(models.Parameter)
