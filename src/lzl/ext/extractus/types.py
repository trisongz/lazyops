from __future__ import annotations

import typing as t
from io import BufferedReader # type: ignore
from lzl.types import BaseModel, Field, Literal

class ExtractousResult(BaseModel):
    """
    Extractous Result
    """
    result: str = Field(None, description = "The extracted result")
    metadata: t.Dict[str, t.Union[t.List[str], t.Any]] = Field(default_factory=dict, description = "The extracted metadata")

    @property
    def text(self) -> str:
        """
        Returns the text for the result
        """
        return self.result

    @property
    def url(self) -> t.Optional[str]:
        """
        Returns the URL
        """
        return self.metadata.get('url')
    
    @property
    def content_type(self) -> t.Optional[str]:
        """
        Returns the content type / mime type
        """
        if self.metadata.get('Content-Type'):
            return self.metadata['Content-Type'][0]
        if self.metadata.get('dc:format'):
            return self.metadata['dc:format'][0].split(';', 1)[0].strip()
        return None
    
    @property
    def filename(self) -> t.Optional[str]:
        """
        Returns the filename
        """
        if self.metadata.get('filename'):
            return self.metadata['filename'][0]
        if self.metadata.get('resourceName'):
            return self.metadata['resourceName'][0]
        if self.metadata.get('Content-Disposition'):
            return self.metadata['Content-Disposition'][0].split(';', 1)[1].split('=', 1)[1].strip()
        return None

    @property
    def num_pages(self) -> t.Optional[int]:
        """
        Returns the number of pages
        """
        if self.metadata.get('num_pages'):
            return int(self.metadata['num_pages'][0])
        if self.metadata.get('xmpTPg:NPages'):
            return int(self.metadata['xmpTPg:NPages'][0])
        return None
    
    @property
    def content_length(self) -> t.Optional[int]:
        """
        Returns the content length
        """
        if self.metadata.get('Content-Length'):
            return int(self.metadata['Content-Length'][0])
        return None
    
    @property
    def created_at(self) -> t.Optional[str]:
        """
        Returns the created at in string format
        """
        if self.metadata.get('created_at'):
            return self.metadata['created_at'][0]
        if self.metadata.get('dcterms:created'):
            return self.metadata['dcterms:created'][0]
        if self.metadata.get('pdf:docinfo:created'):
            return self.metadata['pdf:docinfo:created'][0]
        return None

    @property
    def modified_at(self) -> t.Optional[str]:
        """
        Returns the modified at in string format
        """
        if self.metadata.get('modified_at'):
            return self.metadata['modified_at'][0]
        if self.metadata.get('dcterms:modified'):
            return self.metadata['dcterms:modified'][0]
        if self.metadata.get('pdf:docinfo:modified'):
            return self.metadata['pdf:docinfo:modified'][0]
        return None


    def __str__(self) -> str:
        """
        Returns the string representation of the result
        """
        return self.result or ''

ExtractorMode = Literal['raw', 'dict', 'string', 'object']
ExtractorResult = t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] |  str | t.Dict[str, t.Union[t.Dict[str, t.Any], t.List[str], t.Any]] | ExtractousResult
PDFOCRStrategy = Literal['NO_OCR', 'OCR_ONLY', 'OCR_AND_TEXT_EXTRACTION', 'AUTO']
