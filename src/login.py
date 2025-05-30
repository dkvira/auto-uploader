import logging
import os
import re

import httpx
from bs4 import BeautifulSoup


class AuthenticatedClient(httpx.Client):
    email = os.getenv("DIGIKALA_EMAIL")
    password = os.getenv("DIGIKALA_PASSWORD")
    proxy = os.getenv("DIGIKALA_PROXY")

    def __init__(self, **kwargs):
        super().__init__(
            proxy=self.proxy,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=False,
            **kwargs,
        )

    def login(self):
        url = "https://sso.digikala.com/auth/"
        params = {
            "return_url": "https://admin.digikala.com/login/accounts/callback",
            "product": "admin",
        }
        payload = {
            "login[email]": self.email,
            "login[password]": self.password,
        }

        response = self.post(
            url,
            data=payload,
            params=params,
            # headers=self.headers,
            timeout=10,
        )

        headers = dict(response.headers or {})
        redirect_url = headers.get("location")
        if redirect_url:
            response = self.get(redirect_url, timeout=30)
            self.cookies = response.cookies
            logging.info(f"Redirected to header location {response.cookies}")
            return response

        soup = BeautifulSoup(response.text, "html.parser")
        soup.find_all("script")

        redirect_url = None
        for script in soup.find_all("script"):
            if "window.location.href" in script.text:
                # Extract URL starting with https://admin.digikala.com/login/
                url_match = re.search(
                    r'https://admin\.digikala\.com/login/[^"]+', script.text
                )
                if url_match:
                    redirect_url = url_match.group(0)
                    logging.info("Login successful")
                break

        if not redirect_url:
            raise Exception("Failed to login")

        response = self.get(redirect_url, timeout=30)
        self.cookies = response.cookies
        return response

    def check_login_redirect(self, response: httpx.Response):
        if response is None:
            return False

        headers = dict(response.headers or {})
        if response.status_code == 302:
            return "/login/accounts/auth" in headers.get("location")

        return True


if __name__ == "__main__":
    import config

    config.config_logger()
    
    print(os.getenv("DIGIKALA_EMAIL"))
    print(os.getenv("DIGIKALA_PASSWORD"))
    print(os.getenv("DIGIKALA_PROXY"))
    
    client = AuthenticatedClient()
    response = client.login()
