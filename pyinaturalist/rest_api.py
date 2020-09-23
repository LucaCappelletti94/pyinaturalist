"""
Code used to access the (read/write, but slow) Rails based API of iNaturalist
See: https://www.inaturalist.org/pages/api+reference
"""
from time import sleep
from typing import Dict, Any, List, BinaryIO, Union

from urllib.parse import urljoin

from pyinaturalist.api_docs import (
    get_observations_params_rest as get_observations_params,
    get_observation_fields_params,
    get_all_observation_fields_params,
    create_observations_params,
    update_observation_params,
    delete_observation_params,
)
from pyinaturalist.constants import THROTTLING_DELAY, INAT_BASE_URL
from pyinaturalist.exceptions import AuthenticationError, ObservationNotFound
from pyinaturalist.api_requests import delete, get, post, put
from pyinaturalist.forge_utils import document_request_params
from pyinaturalist.request_params import (
    OBSERVATION_FORMATS,
    REST_OBS_ORDER_BY_PROPERTIES,
    check_deprecated_params,
    validate_multiple_choice_param,
)
from pyinaturalist.response_format import convert_lat_long_to_float


def get_access_token(
    username: str, password: str, app_id: str, app_secret: str, user_agent: str = None
) -> str:
    """Get an access token using the user's iNaturalist username and password.
    You still need an iNaturalist app to do this.

    **API reference:** https://www.inaturalist.org/pages/api+reference#auth

    Example:
        >>> access_token = get_access_token('...')
        >>> headers = {"Authorization": f"Bearer {access_token}"}

    Args:
        username: iNaturalist username
        password: iNaturalist password
        app_id: iNaturalist application ID
        app_secret: iNaturalist application secret
        user_agent: a user-agent string that will be passed to iNaturalist.
    """
    payload = {
        "client_id": app_id,
        "client_secret": app_secret,
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    response = post(
        "{base_url}/oauth/token".format(base_url=INAT_BASE_URL),
        json=payload,
        user_agent=user_agent,
    )
    try:
        return response.json()["access_token"]
    except KeyError:
        raise AuthenticationError("Authentication error, please check credentials.")


@document_request_params(get_observations_params)
def get_observations(user_agent: str = None, **kwargs) -> Union[List, str]:
    """Get observation data, optionally in an alternative format. Also see
    :py:func:`.get_geojson_observations` for GeoJSON format (not included here because it wraps
    a separate API endpoint).

    **API reference:** https://www.inaturalist.org/pages/api+reference#get-observations

    Example:

        >>> get_observations(id=45414404, format="atom")

        .. admonition:: Example Response (atom)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.atom
                :language: xml

        .. admonition:: Example Response (csv)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.csv

        .. admonition:: Example Response (dwc)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.dwc
                :language: xml

        .. admonition:: Example Response (json)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.json
                :language: json

        .. admonition:: Example Response (kml)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.kml
                :language: xml

        .. admonition:: Example Response (widget)
            :class: toggle

            .. literalinclude:: ../sample_data/get_observations.js
                :language: javascript

    Returns:
        Return type will be ``dict`` for the ``json`` response format, and ``str`` for all
        others.
    """
    response_format = kwargs.pop("response_format", "json")
    if response_format == "geojson":
        raise ValueError("For geojson format, use pyinaturalist.node_api.get_geojson_observations")
    if response_format not in OBSERVATION_FORMATS:
        raise ValueError("Invalid response format")
    validate_multiple_choice_param(kwargs, "order_by", REST_OBS_ORDER_BY_PROPERTIES)

    response = get(
        urljoin(INAT_BASE_URL, "observations.{}".format(response_format)),
        params=kwargs,
        user_agent=user_agent,
    )

    if response_format == "json":
        return convert_lat_long_to_float(response.json())
    else:
        return response.text


@document_request_params(get_observation_fields_params)
def get_observation_fields(user_agent: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Search observation fields. Observation fields are basically typed data fields that
    users can attach to observation.

    **API reference:** https://www.inaturalist.org/pages/api+reference#get-observation_fields

    Example:

        >>> get_observation_fields(q='sex')

        .. admonition:: Example Response
            :class: toggle

            .. literalinclude:: ../sample_data/get_observation_fields_page1.json
                :language: javascript

    Returns:
        Observation fields as a list of dicts
    """
    kwargs = check_deprecated_params(kwargs)
    response = get(
        "{base_url}/observation_fields.json".format(base_url=INAT_BASE_URL),
        params=kwargs,
        user_agent=user_agent,
    )
    return response.json()


@document_request_params(get_all_observation_fields_params)
def get_all_observation_fields(**kwargs) -> List[Dict[str, Any]]:
    """
    Like :py:func:`.get_observation_fields()`, but handles pagination for you.

    Returns:
        Observation fields as a list of dicts
    """
    results = []  # type: List[Dict[str, Any]]
    page = 1

    while True:
        r = get_observation_fields(page=page, **kwargs)

        if not r:
            return results

        results += r
        page += 1
        sleep(THROTTLING_DELAY)


def put_observation_field_values(
    observation_id: int,
    observation_field_id: int,
    value: Any,
    access_token: str,
    user_agent: str = None,
) -> Dict[str, Any]:
    # TODO: Also implement a put_or_update_observation_field_values() that deletes then recreates the field_value?
    # TODO: Write example use in docstring.
    # TODO: Return some meaningful exception if it fails because the field is already set.
    # TODO: Also show in example  to obtain the observation_field_id?
    # TODO: What happens when parameters are invalid
    # TODO: It appears pushing the same value/pair twice in a row (but deleting it meanwhile via the UI)...
    # TODO: ...triggers an error 404 the second time (report to iNaturalist?)
    """Set an observation field (value) on an observation.
    Will fail if this observation_field is already set for this observation.

    **API reference:** https://www.inaturalist.org/pages/api+reference#put-observation_field_values-id

    Example:
            >>> put_observation_field_values(
            >>>     observation_id=7345179,
            >>>     observation_field_id=9613,
            >>>     value=250,
            >>>     access_token=token,
            >>> )

        .. admonition:: Example Response
            :class: toggle

            .. literalinclude:: ../sample_data/put_observation_field_value_result.json
                :language: javascript

    Args:
        observation_id: ID of the observation receiving this observation field value
        observation_field_id: ID of the observation field for this observation field value
        value: Value for the observation field
        access_token: access_token: The access token, as returned by :func:`get_access_token()`
        user_agent: A user-agent string that will be passed to iNaturalist.

    Returns:
        The nwely updated field value record
    """

    payload = {
        "observation_field_value": {
            "observation_id": observation_id,
            "observation_field_id": observation_field_id,
            "value": value,
        }
    }

    response = put(
        "{base_url}/observation_field_values/{id}".format(
            base_url=INAT_BASE_URL, id=observation_field_id
        ),
        access_token=access_token,
        user_agent=user_agent,
        json=payload,
    )

    response.raise_for_status()
    return response.json()


# TODO: Implement `observation_field_values_attributes`, and simplify nested data structures
# TODO: implement `local_photos` and support both local file path(s) and object(s)
@document_request_params(create_observations_params)
def create_observations(
    params: Dict[str, Dict[str, Any]], access_token: str, user_agent: str = None, **kwargs
) -> List[Dict[str, Any]]:
    """Create one or more observations.

    **API reference:** https://www.inaturalist.org/pages/api+reference#post-observations

    Example:
        >>> token = get_access_token('...')
        >>> create_observations(
        >>>     access_token=token,
        >>>     species_guess='Pieris rapae',
        >>> )

        .. admonition:: Example Response
            :class: toggle

            .. literalinclude:: ../sample_data/create_observation_result.json
                :language: javascript

        .. admonition:: Example Response (failure)
            :class: toggle

            .. literalinclude:: ../sample_data/create_observation_fail.json
                :language: javascript

    Returns:
        JSON response containing the newly created observation(s)

    Raises:
        :py:exc:`requests.HTTPError`, if the call is not successful. iNaturalist returns an
        error 422 (unprocessable entity) if it rejects the observation data (for example an
        observation date in the future or a latitude > 90. In that case the exception's
        `response` attribute give details about the errors.

    TODO investigate: according to the doc, we should be able to pass multiple observations (in an array, and in
    renaming observation to observations, but as far as I saw they are not created (while a status of 200 is returned)
    """
    # This is the one Boolean parameter that's specified as an int, for some reason
    if "ignore_photos" in kwargs:
        kwargs["ignore_photos"] = int(kwargs["ignore_photos"])
    kwargs = check_deprecated_params(kwargs)
    if "observation" not in kwargs:
        kwargs = {"observation": kwargs}

    response = post(
        url="{base_url}/observations.json".format(base_url=INAT_BASE_URL),
        json=params,
        access_token=access_token,
        user_agent=user_agent,
    )
    response.raise_for_status()
    return response.json()


@document_request_params(update_observation_params)
def update_observation(
    observation_id: int, params: Dict[str, Any], access_token: str, user_agent: str = None, **kwargs
) -> List[Dict[str, Any]]:
    """
    Update a single observation.

    **API reference:** https://www.inaturalist.org/pages/api+reference#put-observations-id

    Example:

        >>> token = get_access_token('...')
        >>> update_observation(
        >>>     17932425,
        >>>     access_token=token,
        >>>     ignore_photos=1,
        >>>     description="updated description!",
        >>> )

        .. admonition:: Example Response
            :class: toggle

            .. literalinclude:: ../sample_data/update_observation_result.json
                :language: javascript

    Returns:
        JSON response containing the newly updated observation(s)

    Raises:
        :py:exc:`requests.HTTPError`, if the call is not successful. iNaturalist returns an
            error 410 if the observation doesn't exists or belongs to another user.
    """
    if "ignore_photos" in kwargs:
        kwargs["ignore_photos"] = int(kwargs["ignore_photos"])
    kwargs = check_deprecated_params(kwargs)
    if "observation" not in kwargs:
        kwargs = {"observation": kwargs}

    response = put(
        url="{base_url}/observations/{id}.json".format(base_url=INAT_BASE_URL, id=observation_id),
        json=params,
        access_token=access_token,
        user_agent=user_agent,
    )
    response.raise_for_status()
    return response.json()


# TODO: Example + sample response
# TODO: Support both local file path(s) and object(s)
def add_photo_to_observation(
    observation_id: int,
    file_object: BinaryIO,
    access_token: str,
    user_agent: str = None,
):
    """Upload a picture and assign it to an existing observation.

    **API reference:** https://www.inaturalist.org/pages/api+reference#post-observation_photos

    Example:


        >>> token = get_access_token('...')
        >>> with open('~/observation_photos/2020_09_01_14003156.jpg', 'rb') as f:
        >>>     add_photo_to_observation(1234, f, access_token=token)

    Args:
        observation_id: the ID of the observation
        file_object: a file-like object for the picture
        access_token: the access token, as returned by :func:`get_access_token()`
        user_agent: a user-agent string that will be passed to iNaturalist.
    """
    data = {"observation_photo[observation_id]": observation_id}
    file_data = {"file": file_object}

    response = post(
        url="{base_url}/observation_photos".format(base_url=INAT_BASE_URL),
        access_token=access_token,
        user_agent=user_agent,
        data=data,
        files=file_data,
    )

    return response.json()


# TODO: test this (success case, wrong_user/403 case)
@document_request_params(delete_observation_params)
def delete_observation(observation_id: int, access_token: str = None, user_agent: str = None):
    """
    Delete an observation.

    **API reference:** https://www.inaturalist.org/pages/api+reference#delete-observations-id

    Example:

        >>> token = get_access_token('...')
        >>> delete_observation(17932425, access_token=token)

    Returns:
        If successful, no response is returned from this endpoint

    Raises:
        :py:exc:`.ObservationNotFound` if the requested observation doesn't exist
        :py:exc:`requests.HTTPError` (403) if the observation belongs to another user
    """
    response = delete(
        url="{base_url}/observations/{id}.json".format(base_url=INAT_BASE_URL, id=observation_id),
        access_token=access_token,
        user_agent=user_agent,
        headers={"Content-type": "application/json"},
    )
    if response.status_code == 404:
        raise ObservationNotFound
    response.raise_for_status()
