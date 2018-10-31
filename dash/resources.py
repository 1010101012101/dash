from copy import copy
import json
import warnings
import os

from .development.base_component import Component
from ._utils import \
    first_key, integrity_hash_from_file, integrity_hash_from_package


def find_unpkg(value, relative_package_paths):
    # find the local file for a unpkg url.
    # The structure of the _js_dist/_css_dist does not allow
    # for easy translation between local and external dependencies.
    v = value.replace('https://unpkg.com/', '')
    s = v.split('/')
    lib, version = s[0].split('@')
    filename = s[-1]
    ext = filename.split('.')[-1]

    for i in relative_package_paths:
        if (i == filename
            and i not in [
                'index.js', 'index.css', 'style.css', 'style.min.css',
                'styles.css', 'styles.min.css']) \
                or (lib in i and version in i and i.endswith(ext)):
            return i


# pylint: disable=old-style-class
class Resources:
    def __init__(self, resource_name, layout):
        self._resources = []
        self.resource_name = resource_name
        self.layout = layout

    def append_resource(self, resource):
        self._resources.append(resource)

    # pylint: disable=too-many-branches
    def _filter_resources(self, all_resources, dev_bundles=False):
        filtered_resources = []
        for s in all_resources:
            filtered_resource = {}
            added = False
            if 'namespace' in s:
                filtered_resource['namespace'] = s['namespace']
            if 'external_url' in s and not self.config.serve_locally:
                filtered_resource['external_url'] = s['external_url']
                filtered_resource['local_file'] = s['relative_package_path']
            elif 'dev_package_path' in s and dev_bundles:
                filtered_resource['relative_package_path'] = (
                    s['dev_package_path']
                )
            elif 'relative_package_path' in s:
                filtered_resource['relative_package_path'] = (
                    s['relative_package_path']
                )
            elif 'absolute_path' in s:
                filtered_resource['absolute_path'] = s['absolute_path']
            elif 'asset_path' in s:
                info = os.stat(s['filepath'])
                filtered_resource['integrity'] = integrity_hash_from_file(
                    s['filepath'])
                filtered_resource['crossorigin'] = 'anonymous'
                filtered_resource['asset_path'] = s['asset_path']
                filtered_resource['ts'] = info.st_mtime
            elif self.config.serve_locally:
                warnings.warn(
                    'A local version of {} is not available'.format(
                        s['external_url']
                    )
                )
                continue
            else:
                raise Exception(
                    '{} does not have a '
                    'relative_package_path, absolute_path, or an '
                    'external_url.'.format(
                        json.dumps(filtered_resource)
                    )
                )

            if 'integrity' not in filtered_resource \
                    and 'namespace' in filtered_resource:
                key, filename = first_key(
                    filtered_resource,
                    'external_url',
                    'dev_package_path',
                    'relative_package_path'
                )
                if isinstance(filename, list):
                    # flatten these dependencies and add a hash for each.
                    for f in filename:
                        local_file = filtered_resource.get('local_file')
                        filename = find_unpkg(f, local_file) \
                            if local_file else f.split('/')[-1]
                        filtered_resources.append({
                            key: f,
                            'integrity': integrity_hash_from_package(
                                filtered_resource['namespace'],
                                filename),
                            'crossorigin': 'anonymous',
                            'namespace': filtered_resource['namespace']
                        })
                        added = True
                else:
                    filename = filtered_resource.get(
                        'local_file', filename.split('/')[-1])
                    filtered_resource['integrity'] = \
                        integrity_hash_from_package(
                            filtered_resource['namespace'],
                            filename
                        )
                    filtered_resource['crossorigin'] = 'anonymous'

            if not added:
                filtered_resources.append(filtered_resource)

        return filtered_resources

    def get_all_resources(self, dev_bundles=False):
        all_resources = []
        if self.config.infer_from_layout:
            all_resources = (
                self.get_inferred_resources() + self._resources
            )
        else:
            all_resources = self._resources

        return self._filter_resources(all_resources, dev_bundles)

    def get_inferred_resources(self):
        namespaces = []
        resources = []
        layout = self.layout

        def extract_resource_from_component(component):
            # pylint: disable=protected-access
            if (isinstance(component, Component) and
                    component._namespace not in namespaces):

                namespaces.append(component._namespace)

                if hasattr(component, self.resource_name):

                    component_resources = copy(
                        getattr(component, self.resource_name)
                    )
                    for r in component_resources:
                        r['namespace'] = component._namespace
                    resources.extend(component_resources)

        extract_resource_from_component(layout)
        for t in layout.traverse():
            extract_resource_from_component(t)
        return resources


class Css:
    # pylint: disable=old-style-class
    def __init__(self, layout=None):
        self._resources = Resources('_css_dist', layout)
        self._resources.config = self.config

    def _update_layout(self, layout):
        self._resources.layout = layout

    def append_css(self, stylesheet):
        self._resources.append_resource(stylesheet)

    def get_all_css(self):
        return self._resources.get_all_resources()

    def get_inferred_css_dist(self):
        return self._resources.get_inferred_resources()

    # pylint: disable=old-style-class, no-init, too-few-public-methods
    class config:
        infer_from_layout = True
        serve_locally = False


class Scripts:  # pylint: disable=old-style-class
    def __init__(self, layout=None):
        self._resources = Resources('_js_dist', layout)
        self._resources.config = self.config

    def _update_layout(self, layout):
        self._resources.layout = layout

    def append_script(self, script):
        self._resources.append_resource(script)

    def get_all_scripts(self, dev_bundles=False):
        return self._resources.get_all_resources(dev_bundles)

    def get_inferred_scripts(self):
        return self._resources.get_inferred_resources()

    # pylint: disable=old-style-class, no-init, too-few-public-methods
    class config:
        infer_from_layout = True
        serve_locally = False
