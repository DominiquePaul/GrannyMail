import os
import uuid
import json
import datetime
import requests


class Pingen:
    """Class to handle the Pingen API

    Most relevant to upload and send letters with one API call. Makes sense to create a class though to handle the authentication and common attributes.
    """

    def __init__(
        self,
        endpoint: str = os.environ["PINGEN_ENDPOINT"],
        client_id: str = os.environ["PINGEN_CLIENT_ID"],
        client_secret: str = os.environ["PINGEN_CLIENT_SECRET"],
        organisation_uuid: str = os.environ["PINGEN_ORGANISATION_UUID"],
        scopes: list[str] = ["letter", "batch", "webhook", "organisation_read"],
    ):
        """instantiates the Pingen class. Used to define general attributes and to get the credentials.

        Args:
            endpoint (str, optional): the core url of the API that we are interacting with. Generally this should be https://api.v2.pingen.com or https://api-staging.v2.pingen.com. Defaults to os.environ["PINGEN_ENDPOINT"].
            client_id (str, optional): Credential for pingen. Required to fetch the token. Defaults to os.environ["PINGEN_CLIENT_ID"].
            client_secret (str, optional): Credential for pingen. Required to fetch the token. Defaults to os.environ["PINGEN_CLIENT_SECRET"].
            organisation_uuid (str, optional): name of your organisation. Can be found in the organisation settings. Defaults to os.environ["PINGEN_ORGANISATION_UUID"].
            scopes (list[str], optional): Defines what the permissions of the object. Defaults to include all possible scopes ["letter", "batch", "webhook", "organisation_read"]. You may want to restrict this.
        """
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.organisation_uuid = organisation_uuid
        self.scopes = scopes
        self.credentials_timeout = None

    def _get_token(self) -> str:
        """Quick way to either return the current token or to fetch a new one.

        Gets the token from the API. If the token is still valid, then it will return the current token. If the token is not valid, then it will fetch a new one.

        Returns:
            str: the bearer access token required for other requests. Needs to be concatenated to 'Bearer: token' for the header.
        """
        # condition to check whether credentials are still valid, if true then nothing to do
        if (
            self.credentials_timeout is not None
            and self.credentials_timeout > datetime.now()
        ):
            return self.access_token
        else:
            endpoint_access = f"{self.endpoint}/auth/access-tokens"
            content = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scopes": self.scopes,
            }
            response = requests.post(
                endpoint_access, headers=content, data=data, timeout=10
            )
            assert response.status_code == 200, "Could not get credentials"
            response_dict = response.json()
            self.timeout = datetime.datetime.now() + datetime.timedelta(
                seconds=response_dict["expires_in"]
            )
            self.access_token = response_dict["access_token"]
            return self.access_token

    def _fetch_letter_upload_url(self) -> tuple[str, str]:
        """Fetches the url and signature where we can upload the letter to.

        This is part of the three step process described by the pingen API

        Returns:
            tuple[str, str]: Returns the url where we can upload the letter to. Also returns the signature that we need to send with the letter upload.
        """
        endpoint_file_upload = f"{self.endpoint}/file-upload"
        response = requests.get(
            endpoint_file_upload,
            headers={
                "Authorization": "Bearer {}".format(self._get_token()),
            },
            timeout=10,
        )
        data = json.loads(response.text)["data"]
        file_url = data["attributes"]["url"]
        file_url_signature = data["attributes"]["url_signature"]
        return file_url, file_url_signature

    def _upload_file(self, file_as_bytes: bytes, file_url: str):
        """Uploads a byte file to the url provided.

        Args:
            file_as_bytes (bytes): the file as bytes, should be a pdf with specifications as described by pingen
            file_url (str): _description_
        """
        requests.put(file_url, data=file_as_bytes, timeout=10)

    def _finalise_letter_upload(
        self,
        file_url: str,
        file_name: str,
        file_url_signature: str,
        auto_send: bool = False,
        color=False,
    ) -> str:
        """The last step of the three step process. This is where we send the letter upload details to pingen.

        Args:
            file_url (str): the url where we uploaded the file to, was supplied by pingen
            file_name (str): the name of the file that we uploaded
            file_url_signature (str): the signature that was supplied by pingen originally in step 1
            auto_send (bool, optional): whether the letter should be sent automatically. Defaults to False.

        Returns:
            str: returns the pingen_letter_uuid of the letter that was created. This is required to send out the letter and also track its status.
        """
        # send letter upload details
        payload = {
            "data": {
                "type": "letters",
                "attributes": {
                    "file_original_name": file_name,
                    "file_url": file_url,
                    "file_url_signature": file_url_signature,
                    "address_position": "left",
                    "auto_send": auto_send,
                    "delivery_product": "fast",
                    "print_mode": "simplex",
                    "print_spectrum": "color" if color else "grayscale",
                },
            }
        }
        endpoint_letters = (
            f"{self.endpoint}/organisations/{self.organisation_uuid}/letters"
        )
        response = requests.post(
            endpoint_letters,
            json.dumps(payload),
            headers={
                "Content-Type": "application/vnd.api+json",
                "Authorization": "Bearer {}".format(self._get_token()),
            },
            timeout=10,
        )
        assert (
            response.status_code == 201
        ), "Could not upload letter. Status code: {}: {}".format(
            response.status_code, response.text
        )
        return json.loads(response.text)["data"]["id"]

    def _send_letter(self, pingen_letter_uuid: str):
        """Send out letters that were not automatically sent out upon upload

        Args:
            letter_uuid (str): name of the letter in pingen
        """
        payload = {
            "data": {
                "id": pingen_letter_uuid,
                "type": "letters",
                "attributes": {
                    "delivery_product": "fast",  # dpag_economy, fast
                    "print_mode": "simplex",  # simplex, duplex
                    "print_spectrum": "color",  # grayscale, color
                },
            }
        }
        send_letter_endpoint = f"{self.endpoint}/organisations/{self.organisation_uuid}/letters/{pingen_letter_uuid}/send"
        response = requests.patch(
            send_letter_endpoint,
            json.dumps(payload),
            headers={
                "Content-Type": "application/vnd.api+json",
                "Authorization": "Bearer {}".format(self._get_token()),
                "Idempotency-Key": str(uuid.uuid4()),
            },
            timeout=10,
        )
        assert (
            response.status_code == 200
        ), f"Could not send letter with uid {pingen_letter_uuid}. Status code: {response.status_code}: {response.text}"

    def upload_and_send_letter(self, file_as_bytes: bytes, file_name: str) -> str:
        """uploads a file to pingen and sends it.

        Follows the 3-Step Process to Create a new letter
        1. Make a GET Request to the (File upload) endpoint to request an upload url.
        2. Send the raw PDF Binary file via PUT Request (Important NOT Form-Post and NO Authorization header) to the url received in Step 1.
        3. Make a POST Request to the Create Letter Endpoint passing the file url and file signature you received in Step 1.
        See here for more: https://api.v2.pingen.com/documentation#tag/letters.general/operation/letters.list

        Args:
            file_as_bytes (bytes): files as bytes, should be a pdf with specifications as described by pingen
            file_name (str): the name of the file/letter, will be used as the name of the letter in pingen

        Returns:
            str: returns the pingen id of the letter that was created. Maybe used to track the status of the letter.
        """
        file_name = file_path.split("/")[-1]
        # step 1
        file_url, file_url_signature = self._fetch_letter_upload_url()
        # step 2
        self._upload_file(file_as_bytes, file_url)
        # step 3
        pingen_letter_uuid = self._finalise_letter_upload(
            file_url, file_name, file_url_signature, auto_send=True
        )
        # self._send_letter(pingen_letter_uuid)
        return pingen_letter_uuid

    def get_letter_details(self, letter_uuid: str) -> dict:
        url = f"{self.endpoint}/organisations/{self.organisation_uuid}/letters/{letter_uuid}"
        r = requests.get(
            url,
            headers={"Authorization": "Bearer {}".format(self._get_token())},
            timeout=10,
        )
        assert (
            r.status_code == 200
        ), f"Could not get letter details for letter with uid {letter_uuid}. Status code: {r.status_code}: {r.text}"
        return r.json()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    pingen = Pingen()
    file_path = "./data/letters/00106968-6967-42a2-95c4-bfbf99845f59.pdf"
    with open(file_path, "rb") as f:
        file_as_bytes = f.read()
    pingen_uid = pingen.upload_and_send_letter(file_as_bytes, "test_file_2.pdf")
    print(pingen_uid)
    print(pingen.get_letter_details(pingen_uid))
    # pingen.get_letter_details("65012395-c251-425f-8acd-9a903e1ac267")
