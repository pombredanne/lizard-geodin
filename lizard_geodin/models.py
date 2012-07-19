# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.txt.
from __future__ import unicode_literals
from collections import defaultdict
import logging

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point as GeosPoint
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from lizard_map import coordinates
import dateutil.parser
import requests

logger = logging.getLogger(__name__)


class Common(models.Model):
    """Abstract base class for the Geodin models.

    There's some automatic machinery in here to make it easy to sync between
    Geodin's json and our database models. ``.update_from_json()`` updates the
    objects's info from a snippet of json. ``.json_from_source_url()``
    reliably grabs the json from the server in case there's a source url
    field.

    There are three attributes you have to fill in to get it to work:

    - ``id_field`` is the field in the json that we use as slug in our
      database. This way our numeric database ID doesn't have to match
      Geodin's.

    - ``field_mapping`` is a dict that maps our model's fields to keys in the
      json dictionary. ``.update_from_json()`` automatically sets those
      fields.

    - ``subitems_mapping`` is the key in the json dictionary that lists the
      subitems. The mapping value is the model that should be created.

    - ``create_subitems`` to tell whether to automatically create subitems.

    """
    # Four attributes to help the automatic json conversion mechanism.
    id_field = 'Id'
    field_mapping = {}
    subitems_mapping = {}
    create_subitems = False
    auto_fill_metadata = False
    # The common fields.
    name = models.CharField(
        _('name'),
        max_length=50,  # Geodin has 40 max.
        null=True,
        blank=True)
    slug = models.SlugField(
        _('slug'),
        help_text=_("Often set automatically from the internal Geodin ID"))
    # TODO: lizard-security dataset foreign key.
    metadata = JSONField(
        _('metadata'),
        help_text=_("Extra metadata provided by Geodin"),
        null=True,
        blank=True)

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.name or self.slug

    def update_from_json(self, the_json):
        self.slug = the_json.pop(self.id_field)
        private_fields = [key for key in the_json if key.startswith('_')]
        for key in private_fields:
            the_json.pop(key)
        for our_field, json_field in self.field_mapping.items():
            if not json_field in the_json:
                # logger.warn("Field %s not available in %r", json_field, self)
                continue
            setattr(self, our_field, the_json.pop(json_field))
        if self.auto_fill_metadata:
            self.metadata = the_json
        else:
            for key in the_json:
                if key not in self.subitems_mapping:
                    logger.debug("Unknown key %s: %s", key, the_json[key])
        self.save()

    @classmethod
    def create_or_update_from_json(cls, the_json, extra_kwargs=None,
                                   already_handled=None):
        if extra_kwargs is None:
            extra_kwargs = {}
        slug = the_json[cls.id_field]
        if already_handled is not None:
            if slug in already_handled[cls]:
                logger.debug("Slug %s already handled, omitting", slug)
                return
        kwargs = {'slug': slug}
        kwargs.update(extra_kwargs)
        obj, is_created = cls.objects.get_or_create(**kwargs)
        obj.update_from_json(the_json)
        logger.debug("Created %r.", obj)
        if already_handled is not None:
            already_handled[cls].append(obj.slug)
        if cls.create_subitems:
            # Create subitems.
            for field, item_class in cls.subitems_mapping.items():
                for json_item in the_json[field]:
                    item_class.create_or_update_from_json(
                        json_item, already_handled=already_handled)
        return obj

    def json_from_source_url(self):
        """Return json from our source_url.

        Note: ``source_url`` is a convention, not every one of our subclasses
        has it. But having this method here is handy.
        """
        if not self.source_url:
            raise ValueError("We need a source_url to update ourselves from.")
        response = requests.get(self.source_url)
        if response.json is None:
            msg = "No json found. HTTP status code was %s, text was \n%s"
            raise ValueError(msg % (response.status_code, response.text))
        return response.json


class DataType(Common):
    """Type of measurement that has been done.

    You need to do something with an investigation type. The data type tells
    you what you did with it, like analyzing it in a geotechnical lab. It
    results in a set of parameters like "dx=..., dy=..., dz=...".
    """
    field_mapping = {'name': 'Name'}

    # Probably TODO: add parameters via extra json field? Including their
    # description?

    class Meta:
        verbose_name = _('data type')
        verbose_name_plural = _('data types')

    def update_from_json(self, the_json):
        # This one is custom!
        self.slug = the_json.pop(self.id_field)
        for our_field, json_field in self.field_mapping.items():
            if not json_field in the_json:
                # logger.warn("Field %s not available in %r", json_field, self)
                continue
            setattr(self, our_field, the_json.pop(json_field))
        # for key in the_json:
        #     if key not in self.subitems_mapping:
        #         logger.debug("Unknown key %s: %s", key, the_json[key])
        self.metadata = {'fields': the_json.pop('Fields')}
        # ^^^ Only used by Measure to show the fields in the .html right now.
        self.save()


class InvestigationType(Common):
    """Source of the measures.

    Source means where the measure physically came from. A ground sample, for
    instance.
    """
    field_mapping = {'name': 'Name'}
    subitems_mapping = {'DataTypes': DataType}
    # create_subitems = True

    class Meta:
        verbose_name = _('investigation type')
        verbose_name_plural = _('investigation types')


class LocationType(Common):
    """Unknown; seems to be for setting attributes."""
    field_mapping = {'name': 'Name'}
    subitems_mapping = {'InvestigationTypes': InvestigationType}
    # create_subitems = True

    class Meta:
        verbose_name = _('location type')
        verbose_name_plural = _('location types')


class Project(Common):
    """Geodin project, it is the starting point for the API.
    """
    field_mapping = {'source_url': 'Url',
                     'name': 'Name'}

    # TODO: field for location of project? For the ProjectsOverview page?
    active = models.BooleanField(
        _('active'),
        help_text=_("Is the project used in this site?"),
        default=False)
    source_url = models.URLField(
        _('source url'),
        help_text=_(
            "Geodin URL for automatically loading this project's data."),
        null=True,
        blank=True)
    api_starting_point = models.ForeignKey(
        'ApiStartingPoint',
        null=True,
        blank=True,
        related_name='location_types')

    class Meta:
        verbose_name = _('project')
        verbose_name_plural = _('projects')
        ordering = ('-active', 'name')

    def get_absolute_url(self):
        return reverse('lizard_geodin_project_view',
                       kwargs={'slug': self.slug})

    def load_from_geodin(self):
        """Load our data from the Geodin API.

        What we receive is a list of location types. In the end, we get
        location types and data types and measures, which are a set of points.

        Note: the hierarchy is depended upon by ``ProjectView`` in our
        ``views.py``.

        """
        the_json = self.json_from_source_url()
        already_handled = defaultdict(list)
        hierarchy = []
        for location_dict in the_json:
            location_type = LocationType.create_or_update_from_json(
                location_dict,
                already_handled=already_handled)
            level1 = {'name': location_type.name,
                      'subitems': []}
            for investigation_dict in location_dict['InvestigationTypes']:
                investigation_type = InvestigationType.create_or_update_from_json(
                    investigation_dict,
                    already_handled=already_handled)
                level2 = {'name': investigation_type.name,
                          'subitems': []}
                for data_dict in investigation_dict['DataTypes']:
                    points = data_dict.pop('Points')
                    data_type = DataType.create_or_update_from_json(
                        data_dict,
                        already_handled=already_handled)
                    level3 = {'name': data_type.name,
                              'measurement_url': None}
                    level2['subitems'].append(level3)
                    if not points:
                        logger.debug("No measurements found.")
                        continue
                    name = ', '.join([self.name,
                                      location_type.name,
                                      investigation_type.name,
                                      data_type.name])
                    measurement, created = Measurement.objects.get_or_create(
                        project=self,
                        location_type=location_type,
                        investigation_type=investigation_type,
                        data_type=data_type)
                    if created:
                        logger.debug("Created a new measurement: %s", name)
                    measurement.name = name
                    measurement.save()
                    for point_dict in points:
                        point = Point.create_or_update_from_json(point_dict)
                        point.measurement = measurement
                        point.set_location_from_xy()
                        point.save()
                    level3['measurement_url'] = measurement.get_absolute_url()
                    level3['measurement_id'] = measurement.id
                    # TODO: this'll be possibly multiple
                    # MeasurementConfigurations instead.
                level1['subitems'].append(level2)
            hierarchy.append(level1)
        if self.metadata is None:
            self.metadata = {}
        self.metadata['hierarchy'] = hierarchy
        self.save()


class ApiStartingPoint(Common):
    """Pointer at the Geodin API startpoint.

    The API starting point has a reload action that grabs the json at
    ``source_url`` and generates/updates the projects that are listed in
    there. By default, new projects are inactive.

    If a project that used to be listed by the API isn't listed anymore, it is
    automatically marked as inactive.
    """

    source_url = models.URLField(
        _('source url'),
        help_text=_("Geodin URL that lists the available projects."),
        null=True,
        blank=True)

    class Meta:
        verbose_name = _('API starting point')
        verbose_name_plural = _('API starting points')

    def load_from_geodin(self):
        """Load our data from the Geodin API.

        What we receive is a list of projects.
        """
        the_json = self.json_from_source_url()
        already_handled = {Project: []}
        for json_item in the_json:
            Project.create_or_update_from_json(
                json_item,
                extra_kwargs={'api_starting_point': self},
                already_handled=already_handled)

        loaded_projects_slugs = already_handled[Project]
        for unknown_project in Project.objects.exclude(
            slug__in=loaded_projects_slugs, api_starting_point=self):
            unknown_project.active = False
            unknown_project.save()


class Measurement(models.Model):
    """The hierarchy of geodin boils down to this really-unnamed class.

    A measurement is unique per project/location/investigation/datatype
    combination.
    """
    name = models.CharField(
        _('name'),
        max_length=255,
        null=True,
        blank=True)
    # slug = models.SlugField(
    #     _('slug'))
    metadata = JSONField(
        _('metadata'),
        help_text=_("Extra metadata provided by Geodin"),
        null=True,
        blank=True)
    project = models.ForeignKey(
        'Project',
        null=True,
        blank=True,
        related_name='measurements')
    location_type = models.ForeignKey(
        'LocationType',
        null=True,
        blank=True,
        related_name='measurements')
    investigation_type = models.ForeignKey(
        'InvestigationType',
        null=True,
        blank=True,
        related_name='measurements')
    data_type = models.ForeignKey(
        'DataType',
        null=True,
        blank=True,
        related_name='measurements')

    class Meta:
        verbose_name = _('measurement')
        verbose_name_plural = _('measurements')

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('lizard_geodin_measurement_view',
                       kwargs={'slug': self.project.slug,
                               'measurement_id': self.id})

    def fields(self):
        return ', '.join(self.data_type.metadata['fields'])


# class MeasurementConfiguration(models.Model):
#     # Point should point at us instead of measurement. If a measurement is
#     # split up into two 'real' measurementconfigurations, duplications of
#     # points is fine, really. Otherwise we get M2M mappings, which is messy.
#     #
#     # A measurementconfiguration should also have a list of fields it needs to
#     # show in the flot graph---perhaps just a piece of json with a mapping?
#     #
#     # Also a filter should be added. For instance filter on
#     # 'maker=companyname'.
#     #
#     # Everything is loaded on sync. So Project's load-json method should be
#     # changed.
#     pass


class Point(Common):
    """Data point."""
    auto_fill_metadata = True
    field_mapping = {'source_url': 'Url',
                     'name': 'Name',
                     'x': 'Xcoord',
                     'y': 'Ycoord',
                     'z': 'Zcoord',
                     }
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    z = models.FloatField(null=True, blank=True)
    measurement = models.ForeignKey(
        'Measurement',
        null=True,
        blank=True,
        related_name='points')
    source_url = models.URLField(
        _('timeseries url'),
        help_text=_(
            "Geodin URL that gives the last couple of days' data."),
        null=True,
        blank=True)
    location = models.PointField(
        null=True,
        blank=True)
    objects = models.GeoManager()

    class Meta:
        verbose_name = _('point with data')
        verbose_name_plural = _('points with data')

    def content_for_display(self):
        """Helper method. Return field/value tuples for showing the content.
        """
        result = {}
        for field_name in self.field_mapping:
            result[field_name] = getattr(self, field_name)
        if self.metadata is not None:
            result.update(self.metadata)
        return sorted(result.items())

    def timeseries(self):
        """Return last couple of days' timeseries data.

        Note that it doesn't have to be one single timeserie. You can have
        (dx, dy, dz), for instance.

        What it returns is a list of dictionaries with 'label' and 'data' for
        flot. You can add 'color' and so yourself afterwards.
        """
        the_json = self.json_from_source_url()
        # Perhaps add caching, it seems to take quite some time.
        lines = defaultdict(list)
        for timestep in the_json:
            timestep.pop('Id')
            date = dateutil.parser.parse(timestep.pop('Date'))
            timestamp_in_seconds = int(date.strftime("%s"))
            timestamp_in_ms = 1000 * timestamp_in_seconds
            # See http://people.iola.dk/olau/flot/examples/time.html
            for key in timestep:
                lines[key].append((timestamp_in_ms, timestep[key]))
        result = []
        for label, data in lines.items():
            flot_line = {'label': label,
                         'data': data}
            result.append(flot_line)
        return result

    def set_location_from_xy(self):
        """x/y is assumed to be in RD."""
        self.location = GeosPoint(coordinates.rd_to_wgs84(self.x, self.y))
