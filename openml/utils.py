import os
import xmltodict
import six
import shutil

import openml._api_calls
from . import config


def extract_xml_tags(xml_tag_name, node, allow_none=True):
    """Helper to extract xml tags from xmltodict.

    Parameters
    ----------
    xml_tag_name : str
        Name of the xml tag to extract from the node.

    node : object
        Node object returned by ``xmltodict`` from which ``xml_tag_name``
        should be extracted.

    allow_none : bool
        If ``False``, the tag needs to exist in the node. Will raise a
        ``ValueError`` if it does not.

    Returns
    -------
    object
    """
    if xml_tag_name in node and node[xml_tag_name] is not None:
        if isinstance(node[xml_tag_name], dict):
            rval = [node[xml_tag_name]]
        elif isinstance(node[xml_tag_name], six.string_types):
            rval = [node[xml_tag_name]]
        elif isinstance(node[xml_tag_name], list):
            rval = node[xml_tag_name]
        else:
            raise ValueError('Received not string and non list as tag item')

        return rval
    else:
        if allow_none:
            return None
        else:
            raise ValueError("Could not find tag '%s' in node '%s'" %
                             (xml_tag_name, str(node)))


def _tag_entity(entity_type, entity_id, tag, untag=False):
    """Function that tags or untags a given entity on OpenML. As the OpenML
       API tag functions all consist of the same format, this function covers
       all entity types (currently: dataset, task, flow, setup, run). Could
       be used in a partial to provide dataset_tag, dataset_untag, etc.

        Parameters
        ----------
        entity_type : str
            Name of the entity to tag (e.g., run, flow, data)

        entity_id : int
            OpenML id of the entity

        tag : str
            The tag

        untag : bool
            Set to true if needed to untag, rather than tag

        Returns
        -------
        tags : list
            List of tags that the entity is (still) tagged with
        """
    legal_entities = {'data', 'task', 'flow', 'setup', 'run'}
    if entity_type not in legal_entities:
        raise ValueError('Can\'t tag a %s' %entity_type)

    uri = '%s/tag' %entity_type
    main_tag = 'oml:%s_tag' %entity_type
    if untag:
        uri = '%s/untag' %entity_type
        main_tag = 'oml:%s_untag' %entity_type

    post_variables = {'%s_id'%entity_type: entity_id, 'tag': tag}
    result_xml = openml._api_calls._perform_api_call(uri, post_variables)

    result = xmltodict.parse(result_xml, force_list={'oml:tag'})[main_tag]

    if 'oml:tag' in result:
        return result['oml:tag']
    else:
        # no tags, return empty list
        return []


def _list_all(listing_call, *args, **filters):
    """Helper to handle paged listing requests.

    Example usage:

    ``evaluations = list_all(list_evaluations, "predictive_accuracy", task=mytask)``
    
    Parameters
    ----------
    listing_call : callable
        Call listing, e.g. list_evaluations.
    *args : Variable length argument list
        Any required arguments for the listing call.
    **filters : Arbitrary keyword arguments
        Any filters that can be applied to the listing function.
        additionally, the batch_size can be specified. This is
        useful for testing purposes.
    Returns
    -------
    dict
    """

    # eliminate filters that have a None value
    active_filters = {key: value for key, value in filters.items() if value is not None}
    page = 0
    result = {}

    # default batch size per paging. This one can be set in filters (batch_size),
    # but should not be changed afterwards. the derived batch_size can be changed.
    BATCH_SIZE_ORIG = 10000
    if 'batch_size' in active_filters:
        BATCH_SIZE_ORIG = active_filters['batch_size']
        del active_filters['batch_size']
    batch_size = BATCH_SIZE_ORIG

    # max number of results to be shown
    LIMIT = None
    offset = 0
    cycle = True
    if 'size' in active_filters:
        LIMIT = active_filters['size']
        del active_filters['size']
    # check if the batch size is greater than the number of results that need to be returned.
    if LIMIT is not None:
        if BATCH_SIZE_ORIG > LIMIT:
            batch_size = LIMIT
    if 'offset' in active_filters:
        offset = active_filters['offset']
        del active_filters['offset']
    while cycle:
        try:
            new_batch = listing_call(
                *args,
                limit=batch_size,
                offset=offset + BATCH_SIZE_ORIG * page,
                **active_filters
            )
        except openml.exceptions.OpenMLServerNoResult:
            # we want to return an empty dict in this case
            break
        result.update(new_batch)
        page += 1
        if LIMIT is not None:
            # check if the number of required results has been achieved
            # always do a 'bigger than' check, in case of bugs to prevent infinite loops
            if len(result) >= LIMIT:
                break
            # check if there are enough results to fulfill a batch
            if BATCH_SIZE_ORIG > LIMIT - len(result):
                batch_size = LIMIT - len(result)

    return result


def _create_cache_directory(key):
    cache = config.get_cache_directory()
    cache_dir = os.path.join(cache, key)
    try:
        os.makedirs(cache_dir)
    except:
        pass
    return cache_dir


def _create_cache_directory_for_id(key, id_):
    """Create the cache directory for a specific ID

    In order to have a clearer cache structure and because every task
    is cached in several files (description, split), there
    is a directory for each task witch the task ID being the directory
    name. This function creates this cache directory.

    This function is NOT thread/multiprocessing safe.

    Parameters
    ----------
    key : str
    
    id_ : int

    Returns
    -------
    str
        Path of the created dataset cache directory.
    """
    cache_dir = os.path.join(
        _create_cache_directory(key), str(id_)
    )
    if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
        pass
    elif os.path.exists(cache_dir) and not os.path.isdir(cache_dir):
        raise ValueError('%s cache dir exists but is not a directory!' % key)
    else:
        os.makedirs(cache_dir)
    return cache_dir


def _remove_cache_dir_for_id(key, cache_dir):
    """Remove the task cache directory

    This function is NOT thread/multiprocessing safe.

    Parameters
    ----------
    key : str
    
    cache_dir : str
    """
    try:
        shutil.rmtree(cache_dir)
    except (OSError, IOError):
        raise ValueError('Cannot remove faulty %s cache directory %s.'
                         'Please do this manually!' % (key, cache_dir))


def _create_lockfiles_dir():
    dir = os.path.join(config.get_cache_directory(), 'locks')
    try:
        os.makedirs(dir)
    except:
        pass
    return dir
