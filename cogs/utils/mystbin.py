# https://github.com/PythonistaGuild/mystbin.py/issues/6
import json
from datetime import datetime
from typing import Optional

import mystbin  # https://pypi.org/project/mystbin.py/
from mystbin.types.responses import PasteResponse


"""
Copyright 2020-Present PythonistaGuild

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""


class MyMystbinPaste(mystbin.Paste):
    @classmethod
    def _from_data(cls, payload: PasteResponse, /):
        if isinstance(payload, str):
            payload: dict = json.loads(payload)
        files = [mystbin.File._from_data(data) for data in payload["files"]]
        return cls(
            id=payload["id"],
            created_at=payload["created_at"],
            expires=payload["expires"],
            files=files,
            views=payload.get("views"),
            last_edited=payload.get("last_edited"),
        )


class MyMystbinClient(mystbin.Client):
    async def create_paste(
        self,
        *,
        filename: str,
        content: str,
        syntax: Optional[str] = None,
        password: Optional[str] = None,
        expires: Optional[datetime] = None,
    ) -> MyMystbinPaste:
        """|coro|

        Create a single file paste on mystb.in.

        Parameters
        -----------
        filename: :class:`str`
            The filename to create.
        content: :class:`str`
            The content of the file you are creating.
        syntax: Optional[:class:`str`]
            The syntax of the file to create, if any.
        password: Optional[:class:`str`]
            The password of the paste, if any.
        expires: Optional[:class:`datetime.datetime`]
            When the paste expires, if any.

        Returns
        --------
        :class:`mystbin.Paste`
            The paste that was created.
        """
        file = mystbin.File(filename=filename, content=content, syntax=syntax)
        data = await self.http._create_paste(
            file=file, password=password, expires=expires
        )
        return MyMystbinPaste._from_data(data)
