from __future__ import annotations

import abc
import typing as t
from io import BytesIO, BufferedReader # type: ignore
from lzl import load
from .types import ExtractorMode, ExtractorResult, PDFOCRStrategy, ExtractousResult

if load.TYPE_CHECKING:
    import extractous
    from lzl.io import FileLike
else:
    extractous = load.lazy_load('extractous', install_missing=True)


# https://github.com/yobix-ai/extractous/blob/336857d55920c81026936252270e46ec87ba0969/extractous-core/src/config.rs#L18
# 500_000

class Extractor(abc.ABC):
    

    @t.overload
    def __init__(
        self,
        
        # OCR Config
        density: t.Optional[int] = ...,
        depth: t.Optional[int] = ...,
        timeout_seconds: t.Optional[int] = ...,
        enable_image_preprocessing: t.Optional[bool] = ...,
        apply_rotation: t.Optional[bool] = ...,
        language: t.Optional[str] = ...,
        **kwargs,
    ):
        """
        Initializes the Extractor
            
            OCR Config Args:
                density (t.Optional[int], optional): The density. Defaults to 300.
                depth (t.Optional[int], optional): The depth. Defaults to 4.
                timeout_seconds (t.Optional[int], optional): The timeout seconds. Defaults to 130.
                enable_image_preprocessing (t.Optional[bool], optional): The enable image preprocessing. Defaults to False.
                apply_rotation (t.Optional[bool], optional): The apply rotation. Defaults to False.
                language (t.Optional[str], optional): The language. Defaults to eng.
        """
        ...

    @t.overload
    def __init__(
        self,
        
        # PDF Config
        ocr_strategy: t.Optional[PDFOCRStrategy] = ...,
        extract_inline_images: t.Optional[bool] = ...,
        extract_unique_inline_images_only: t.Optional[bool] = ...,
        extract_marked_content: t.Optional[bool] = ...,
        extract_annotation_text: t.Optional[bool] = ...,        
        **kwargs,
    ):
        """
        Initializes the Extractor
            
            PDF Config Args:
                ocr_strategy (t.Optional[PDFOCRStrategy], optional): The OCR strategy. Defaults to 'AUTO'.
                extract_inline_images (t.Optional[bool], optional): The extract inline images. Defaults to False.
                extract_unique_inline_images_only (t.Optional[bool], optional): The extract unique inline images only. Defaults to False.
                extract_marked_content (t.Optional[bool], optional): The extract marked content. Defaults to False.
                extract_annotation_text (t.Optional[bool], optional): The extract annotation text. Defaults to False.
        """
        ...
            
    @t.overload
    def __init__(
        self,
        
        # Office Config
        extract_macros: t.Optional[bool] = ...,
        include_deleted_content: t.Optional[bool] = ...,
        include_move_from_content: t.Optional[bool] = ...,
        include_shape_based_content: t.Optional[bool] = ...,
        include_headers_and_footers: t.Optional[bool] = ...,
        include_missing_rows: t.Optional[bool] = ...,
        include_slide_notes: t.Optional[bool] = ...,
        include_slide_master_content: t.Optional[bool] = ...,
        concatenate_phonetic_runs: t.Optional[bool] = ...,
        extract_all_alternatives_from_msg: t.Optional[bool] = ...,
        **kwargs,
    ):
        """
        Initializes the Extractor
            
            Office Config Args:
                extract_macros (t.Optional[bool], optional): The extract macros. Defaults to None.
                include_deleted_content (t.Optional[bool], optional): The include deleted content. Defaults to False.
                include_move_from_content (t.Optional[bool], optional): The include move from content. Defaults to False.
                include_shape_based_content (t.Optional[bool], optional): The include shape based content. Defaults to True.
                include_headers_and_footers (t.Optional[bool], optional): The include headers and footers. Defaults to False.
                include_missing_rows (t.Optional[bool], optional): The include missing rows. Defaults to False.
                include_slide_notes (t.Optional[bool], optional): The include slide notes. Defaults to True.
                include_slide_master_content (t.Optional[bool], optional): The include slide master content. Defaults to True.
                concatenate_phonetic_runs (t.Optional[bool], optional): The concatenate phonetic runs. Defaults to True.
                extract_all_alternatives_from_msg (t.Optional[bool], optional): The extract all alternatives from msg. Defaults to False.
        """
        ...

    
    @t.overload
    def __init__(
        self,
        max_string_length: t.Optional[int] = ...,
        default_encoding: t.Optional[str] = 'utf-8',
        default_chunk_size: t.Optional[int] = ...,
        default_mode: t.Optional[ExtractorMode] = 'object',
        **kwargs,
    ):
        """
        Initializes the Extractor
            
            Class Config Args:
                max_string_length (t.Optional[int], optional): The maximum string length. Defaults to 500_000.
                default_encoding (t.Optional[str], optional): The default encoding. Defaults to 'utf-8'.
                default_chunk_size (t.Optional[int], optional): The default chunk size. Defaults to 4096.
                default_mode (t.Optional[ExtractorMode], optional): The default mode. Defaults to 'object'.
        """
        ...
    

    def __init__(
        self,
        max_string_length: t.Optional[int] = None,
        default_encoding: t.Optional[str] = 'utf-8',
        default_chunk_size: t.Optional[int] = 4096,
        default_mode: t.Optional[ExtractorMode] = 'object',
        **kwargs,
    ):
        self.default_encoding = default_encoding
        self.default_chunk_size = default_chunk_size
        self.default_mode = default_mode
        self.ocr_config = extractous.TesseractOcrConfig()
        self.pdf_config = extractous.PdfParserConfig()
        self.office_config = extractous.OfficeParserConfig()
        self.set_ocr_config(**kwargs)
        self.set_pdf_config(**kwargs)
        self.set_office_config(**kwargs)
        self.api = extractous.Extractor()
        self.api.set_ocr_config(self.ocr_config)
        self.api.set_pdf_config(self.pdf_config)
        self.api.set_office_config(self.office_config)        
        if max_string_length is not None: self.api.set_extract_string_max_length(max_string_length)
    

    """
    Utilities
    """

    def _get_string_from_reader(self, reader: BufferedReader, encoding: t.Optional[str] = None, chunk_size: t.Optional[int] = None) -> str:
        """
        Gets a string from a reader
        """
        if encoding is None: encoding = self.default_encoding
        if chunk_size is None: chunk_size = self.default_chunk_size
        result = ''
        buffer = reader.read(chunk_size)
        while len(buffer) > 0:
            result += buffer.decode(encoding, errors = 'ignore')
            buffer = reader.read(chunk_size)
        return result

    def _get_output(self, reader: BufferedReader, metadata: t.Dict[str, t.Union[t.List[str], t.Any]], mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        # sourcery skip: class-extract-method
        """
        Gets the output

        Args:
            reader (BufferedReader): The reader to get the output from
            metadata (t.Dict[str, t.Union[t.List[str], t.Any]]): The metadata to get the output from
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.

            Returns:
                t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] |  t.Dict[str, t.Union[t.Dict[str, t.Any], t.List[str], t.Any]] | ExtractousResult: The output
        """
        if mode is None: mode = self.default_mode
        if mode == 'raw': return reader, metadata
        result = self._get_string_from_reader(reader)
        if mode == 'string': return result
        if mode == 'dict': return {'result': result, 'metadata': metadata}
        return ExtractousResult(result=result, metadata=metadata)


    """
    Mirror the Extractor API
    """

    def set_extract_string_max_length(self, max_length: int):
        """
        Sets the maximum length of the extracted string
        """
        self.api.set_extract_string_max_length(max_length)

    def extract_bytes(self, buffer: BytesIO | bytearray, mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        """
        Extracts bytes to string
        
        Args:
            buffer (BytesIO | bytearray): The buffer to extract
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.
        
            Returns:
                t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] | ExtractousResult: The extracted result
        """
        if isinstance(buffer, BytesIO):
            buffer = buffer.getvalue()
        reader, metadata = self.api.extract_bytes(buffer)
        return self._get_output(reader = reader, metadata = metadata, mode = mode)

    def extract_file(self, file_path: str | 'FileLike', mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        """
        Extracts a file

        Args:
            file_path (str | FileLike): The file path or file-like object to extract
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.

        Returns:
            t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] | ExtractousResult: The extracted result
        """
        # We're going to use the File class to get the file path
        
        from lzl.io import File
        file_path = File(file_path)
        buffer = bytearray(file_path.read())
        return self.extract_bytes(buffer, mode = mode)

    def extract_file_to_string(self, file_path: str | 'FileLike', mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        """
        Extracts a File to string

        Args:
            file_path (str | FileLike): The file path or file-like object to extract
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.

        Returns:
            t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] | ExtractousResult: The extracted result
        """
        reader, metadata = self.api.extract_file_to_string(file_path)
        return self._get_output(reader = reader, metadata = metadata, mode = mode)


    def extract_url(self, url: str, mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        """
        Extracts a URL

        Args:
            url (str): The URL to extract
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.

        Returns:
            t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] | ExtractousResult: The extracted result
        """
        reader, metadata = self.api.extract_url(url)
        metadata['url'] = url
        return self._get_output(reader = reader, metadata = metadata, mode = mode)

    def extract_url_to_string(self, url: str, mode: t.Optional[ExtractorMode] = None) -> ExtractorResult:
        """
        Extracts a URL to string

        Args:
            url (str): The URL to extract
            mode (t.Optional[ExtractorMode], optional): The mode to use. Defaults to None.

        Returns:
            t.Tuple[BufferedReader | t.Dict[str, t.Union[t.List[str], t.Any]]] | ExtractousResult: The extracted result
        """
        reader, metadata = self.api.extract_url_to_string(url)
        metadata['url'] = url
        return self._get_output(reader = reader, metadata = metadata, mode = mode)


    """
    Configuration Methods
    """
            
    def set_ocr_config(
        self,
        density: t.Optional[int] = None,
        depth: t.Optional[int] = None,
        timeout_seconds: t.Optional[int] = None,
        enable_image_preprocessing: t.Optional[bool] = None,
        apply_rotation: t.Optional[bool] = None,
        language: t.Optional[str] = None,
        **kwargs,
    ):
        """
        Sets the OCR config

        Args:
            density (t.Optional[int], optional): The density. Defaults to 300.
            depth (t.Optional[int], optional): The depth. Defaults to 4.
            timeout_seconds (t.Optional[int], optional): The timeout seconds. Defaults to 130.
            enable_image_preprocessing (t.Optional[bool], optional): The enable image preprocessing. Defaults to False.
            apply_rotation (t.Optional[bool], optional): The apply rotation. Defaults to False.
            language (t.Optional[str], optional): The language. Defaults to eng.
        
        """
        if density is not None: self.ocr_config.set_density(density)
        if depth is not None: self.ocr_config.set_depth(depth)
        if timeout_seconds is not None: self.ocr_config.set_timeout_seconds(timeout_seconds)
        if enable_image_preprocessing is not None: self.ocr_config.set_enable_image_preprocessing(enable_image_preprocessing)
        if apply_rotation is not None: self.ocr_config.set_apply_rotation(apply_rotation)
        if language is not None: self.ocr_config.set_language(language)

    def set_pdf_config(
        self,
        ocr_strategy: t.Optional[PDFOCRStrategy] = None,
        extract_inline_images: t.Optional[bool] = None,
        extract_unique_inline_images_only: t.Optional[bool] = None,
        extract_marked_content: t.Optional[bool] = None,
        extract_annotation_text: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Sets the PDF config

        Args:
            ocr_strategy (t.Optional[PDFOCRStrategy], optional): The OCR strategy. Defaults to 'AUTO'.
            extract_inline_images (t.Optional[bool], optional): The extract inline images. Defaults to False.
            extract_unique_inline_images_only (t.Optional[bool], optional): The extract unique inline images only. Defaults to False.
            extract_marked_content (t.Optional[bool], optional): The extract marked content. Defaults to False.
            extract_annotation_text (t.Optional[bool], optional): The extract annotation text. Defaults to False.
        """
        if ocr_strategy is not None: self.pdf_config.set_ocr_strategy(ocr_strategy)
        if extract_inline_images is not None: self.pdf_config.set_extract_inline_images(extract_inline_images)
        if extract_unique_inline_images_only is not None: self.pdf_config.set_extract_unique_inline_images_only(extract_unique_inline_images_only)
        if extract_marked_content is not None: self.pdf_config.set_extract_marked_content(extract_marked_content)
        if extract_annotation_text is not None: self.pdf_config.set_extract_annotation_text(extract_annotation_text)

    def set_office_config(
        self,
        extract_macros: t.Optional[bool] = None,
        include_deleted_content: t.Optional[bool] = None,
        include_move_from_content: t.Optional[bool] = None,
        include_shape_based_content: t.Optional[bool] = None,
        include_headers_and_footers: t.Optional[bool] = None,
        include_missing_rows: t.Optional[bool] = None,
        include_slide_notes: t.Optional[bool] = None,
        include_slide_master_content: t.Optional[bool] = None,
        concatenate_phonetic_runs: t.Optional[bool] = None,
        extract_all_alternatives_from_msg: t.Optional[bool] = None,
        **kwargs,
    ):
        """
        Sets the Office config

        Args:
            extract_macros (t.Optional[bool], optional): The extract macros. Defaults to None.
            include_deleted_content (t.Optional[bool], optional): The include deleted content. Defaults to False.
            include_move_from_content (t.Optional[bool], optional): The include move from content. Defaults to False.
            include_shape_based_content (t.Optional[bool], optional): The include shape based content. Defaults to True.
            include_headers_and_footers (t.Optional[bool], optional): The include headers and footers. Defaults to False.
            include_missing_rows (t.Optional[bool], optional): The include missing rows. Defaults to False.
            include_slide_notes (t.Optional[bool], optional): The include slide notes. Defaults to True.
            include_slide_master_content (t.Optional[bool], optional): The include slide master content. Defaults to True.
            concatenate_phonetic_runs (t.Optional[bool], optional): The concatenate phonetic runs. Defaults to True.
            extract_all_alternatives_from_msg (t.Optional[bool], optional): The extract all alternatives from msg. Defaults to False.
        """
        if extract_macros is not None: self.office_config.set_extract_macros(extract_macros)
        if include_deleted_content is not None: self.office_config.set_include_deleted_content(include_deleted_content)
        if include_move_from_content is not None: self.office_config.set_include_move_from_content(include_move_from_content)
        if include_shape_based_content is not None: self.office_config.set_include_shape_based_content(include_shape_based_content)
        if include_headers_and_footers is not None: self.office_config.set_include_headers_and_footers(include_headers_and_footers)
        if include_missing_rows is not None: self.office_config.set_include_missing_rows(include_missing_rows)
        if include_slide_notes is not None: self.office_config.set_include_slide_notes(include_slide_notes)
        if include_slide_master_content is not None: self.office_config.set_include_slide_master_content(include_slide_master_content)
        if concatenate_phonetic_runs is not None: self.office_config.set_concatenate_phonetic_runs(concatenate_phonetic_runs)
        if extract_all_alternatives_from_msg is not None: self.office_config.set_extract_all_alternatives_from_msg(extract_all_alternatives_from_msg)

    def set_encoding(
        self,
        encoding: t.Optional[str] = None,
        **kwargs,
    ):
        """
        Sets the encoding
        
        Args:
            encoding (t.Optional[str], optional): The encoding. Defaults to None.
        """
        if encoding is not None: self.api.set_encoding(encoding)

    

