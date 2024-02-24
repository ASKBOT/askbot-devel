from collections import OrderedDict
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.xml_serializer import Serializer
from django.db import connections, router, DEFAULT_DB_ALIAS
from io import StringIO

class XMLExportSerializer(Serializer):
    def serialize(self, queryset, **options):
        """
        Serialize a queryset.
        Copy-paste from the base serializer with a minor difference
        commented below
        """
        self.options = options

        self.stream = options.pop("stream", StringIO())
        self.selected_fields = options.pop("fields", None)
        self.use_natural_foreign_keys = options.pop("use_natural_foreign_keys", False)

        self.start_serialization()
        for obj in queryset:
            self.start_object(obj)
            #the line below is the only one that was changed
            for field in obj._meta.fields:
                if field.serialize:
                    if field.remote_field is None:
                        if self.selected_fields is None or field.attname in self.selected_fields:
                            self.handle_field(obj, field)
                    else:
                        if self.selected_fields is None or field.attname[:-3] in self.selected_fields:
                            self.handle_fk_field(obj, field)
            for field in obj._meta.many_to_many:
                if field.serialize:
                    if self.selected_fields is None or field.attname in self.selected_fields:
                        self.handle_m2m_field(obj, field)
            self.end_object(obj)
        self.end_serialization()
        return self.getvalue()


class Command(BaseCommand):
    help = ("Output the contents of the OSQA database as XML fixture of the given "
            "format (using each model's default manager unless --all is "
            "specified).")
    args = '[appname appname.ModelName ...]'

    def add_arguments(self, parser):
        parser.add_argument('--indent', default=4, dest='indent', type=int,
            help='Specifies the indent level to use when pretty-printing output')
        parser.add_argument('--database', action='store', dest='database',
            default=DEFAULT_DB_ALIAS, help='Nominates a specific database to load '
                'fixtures into. Defaults to the "default" database.')
        parser.add_argument('-e', '--exclude', dest='exclude',action='append', default=['sessions', 'contenttypes'],
            help='An appname or appname.ModelName to exclude (use multiple --exclude to exclude multiple apps/models).')
        parser.add_argument('--natural-foreign', action='store_true', dest='use_natural_foreign_keys', default=False,
            help='Use natural keys if they are available.')
        parser.add_argument('-a', '--all', action='store_true', dest='use_base_manager', default=False,
            help="Use Django's base manager to dump all models stored in the database, including those that would otherwise be filtered or modified by a custom manager.")

    def handle(self, *app_labels, **options):
        from django.apps import apps

        indent = options.get('indent', None)
        using = options.get('database', DEFAULT_DB_ALIAS)
        connection = connections[using]
        excludes = options.get('exclude',[])
        show_traceback = options.get('traceback', False)
        use_natural_foreign_keys = options.get('use_natural_foreign_keys', False)
        use_base_manager = options.get('use_base_manager', False)

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = apps.get_model(app_label, model_name)
                if not model_obj:
                    raise CommandError('Unknown model in excludes: %s' % exclude)
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = apps.get_app(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    raise CommandError('Unknown app in excludes: %s' % exclude)

        if len(app_labels) == 0:
            app_list = OrderedDict((app, None) for app in apps.get_apps() if app not in excluded_apps)
        else:
            app_list = OrderedDict()
            for label in app_labels:
                try:
                    app_label, model_label = label.split('.')
                    try:
                        app = apps.get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    model = apps.get_model(app_label, model_label)
                    if model is None:
                        raise CommandError(f"Unknown model: {app_label}.{model_label}")

                    if app in list(app_list.keys()):
                        if app_list[app] and model not in app_list[app]:
                            app_list[app].append(model)
                    else:
                        app_list[app] = [model]
                except ValueError:
                    # This is just an app - no model qualifier
                    app_label = label
                    try:
                        app = apps.get_app(app_label)
                    except ImproperlyConfigured:
                        raise CommandError("Unknown application: %s" % app_label)
                    if app in excluded_apps:
                        continue
                    app_list[app] = None

        # Now collate the objects to be serialized.
        objects = []
        for model in sort_dependencies(list(app_list.items())):
            if model in excluded_models:
                continue
            if not model._meta.proxy and router.allow_migrate(using, model):
                if use_base_manager:
                    objects.extend(model._base_manager.using(using).all())
                else:
                    objects.extend(model._default_manager.using(using).all())

        try:
            serializer = XMLExportSerializer()
            return serializer.serialize(objects, indent=indent, use_natural_foreign_keys=use_natural_foreign_keys)
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)

def sort_dependencies(app_list):
    """Sort a list of app,modellist pairs into a single list of models.

    The single list of models is sorted so that any model with a natural key
    is serialized before a normal model, and any model with a natural key
    dependency has it's dependencies serialized first.
    """
    from django.apps import apps
    # Process the list of models, and get the list of dependencies
    model_dependencies = []
    models = set()
    for app, model_list in app_list:
        if model_list is None:
            model_list = apps.get_models(app)

        for model in model_list:
            models.add(model)
            # Add any explicitly defined dependencies
            if hasattr(model, 'natural_key'):
                deps = getattr(model.natural_key, 'dependencies', [])
                if deps:
                    deps = [apps.get_model(*d.split('.')) for d in deps]
            else:
                deps = []

            # Now add a dependency for any FK or M2M relation with
            # a model that defines a natural key
            for field in model._meta.fields:
                if hasattr(field.remote_field, 'to'):
                    rel_model = field.remote_field.to
                    if hasattr(rel_model, 'natural_key'):
                        deps.append(rel_model)
            for field in model._meta.many_to_many:
                rel_model = field.remote_field.to
                if hasattr(rel_model, 'natural_key'):
                    deps.append(rel_model)
            model_dependencies.append((model, deps))

    model_dependencies.reverse()
    # Now sort the models to ensure that dependencies are met. This
    # is done by repeatedly iterating over the input list of models.
    # If all the dependencies of a given model are in the final list,
    # that model is promoted to the end of the final list. This process
    # continues until the input list is empty, or we do a full iteration
    # over the input models without promoting a model to the final list.
    # If we do a full iteration without a promotion, that means there are
    # circular dependencies in the list.
    model_list = []
    while model_dependencies:
        skipped = []
        changed = False
        while model_dependencies:
            model, deps = model_dependencies.pop()

            # If all of the models in the dependency list are either already
            # on the final model list, or not on the original serialization list,
            # then we've found another model with all it's dependencies satisfied.
            found = True
            for candidate in ((d not in models or d in model_list) for d in deps):
                if not candidate:
                    found = False
            if found:
                model_list.append(model)
                changed = True
            else:
                skipped.append((model, deps))
        if not changed:
            raise CommandError("Can't resolve dependencies for %s in serialized app list." %
                ', '.join(f'{model._meta.app_label}.{model._meta.object_name}'
                for model, deps in sorted(skipped, key=lambda obj: obj[0].__name__))
            )
        model_dependencies = skipped

    return model_list
