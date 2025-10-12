from typing import List
from os import path, unlink
import subprocess
import tempfile
import logging


class FileService:
    def compress_pdf_buffer(self, pdf_bytes: bytes, quality: str) -> bytes:
        logging.debug(
            f"Compressing {len(pdf_bytes)} bytes with quality={quality} in buffer"
        )

        gs_cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-dDetectDuplicateImages=true",
            "-dRemoveOPComments=true",
            "-dCompressFonts=true",
            "-dDiscardComments=true",
            "-dDiscardDocInfo=true",
            "-dFILTERTEXTANNOTATIONS=true",
            "-dFILTERIMAGEANNOTATIONS=true",
            "-sOutputFile=-",
            "-",
        ]
        gs_process: subprocess.Popen = None

        try:
            gs_process = subprocess.Popen(
                gs_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            gs_output, gs_err = gs_process.communicate(input=pdf_bytes, timeout=60)
            if gs_process.returncode != 0:
                raise RuntimeError(
                    f"Error to compress file: {gs_err.decode('utf-8', 'ignore')}"
                )

            if not gs_output:
                raise RuntimeError("Compression failed: no output generated")

            return gs_output
        except subprocess.TimeoutExpired:
            if gs_process:
                gs_process.kill()
                gs_process.wait()
            raise RuntimeError("Compression took too long")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {str(e)}")

    def compress_pdf_tmp(self, pdf_bytes: bytes, quality: str) -> bytes:
        logging.debug(
            f"Compressing {len(pdf_bytes)} bytes with quality={quality} in tmp disk"
        )

        input_path = None
        output_path = None
        output_compress_path = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as input_file:
                input_file.write(pdf_bytes)
                input_path = input_file.name

            with tempfile.NamedTemporaryFile(
                suffix="_gs.pdf", delete=False
            ) as output_file:
                output_path = output_file.name

            with tempfile.NamedTemporaryFile(
                suffix="_qpdf.pdf", delete=False
            ) as output_compress_file:
                output_compress_path = output_compress_file.name

            mono_quality = 300
            color_image_quality = 96
            gray_image_quality = 96

            match quality:
                case "printer":
                    mono_quality = 600
                    color_image_quality = 150
                    gray_image_quality = 150
                case "ebook":
                    mono_quality = 300
                    color_image_quality = 96
                    gray_image_quality = 96
                case "screen":
                    mono_quality = 150
                    color_image_quality = 72
                    gray_image_quality = 72

            gs_cmd = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.7",
                f"-dPDFSETTINGS=/{quality}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                "-dDetectDuplicateImages=true",
                "-dRemoveDuplicateImages=true",
                "-dRemoveOPComments=true",
                "-dCompressFonts=true",
                "-dSubsetFonts=true",
                "-dCompressPages=true",
                "-dEmbedAllFonts=true",
                "-dDownsampleColorImages=true",
                f"-dColorImageResolution={color_image_quality}",
                "-dColorImageDownsampleType=/Bicubic",
                "-dAutoFilterColorImages=false",
                "-dColorImageFilter=/DCTEncode",
                "-dDownsampleGrayImages=true",
                f"-dGrayImageResolution={gray_image_quality}",
                "-dGrayImageDownsampleType=/Bicubic",
                "-dAutoFilterGrayImages=false",
                "-dGrayImageFilter=/DCTEncode",
                "-dDownsampleMonoImages=true",
                f"-dMonoImageResolution={mono_quality}",
                "-dMonoImageDownsampleType=/Bicubic",
                "-dDiscardComments=true",
                "-dDiscardDocInfo=true",
                "-dFilterTextAnnotations=true",
                "-dFilterImageAnnotations=true",
                f"-sOutputFile={output_path}",
                input_path,
            ]

            gs_process = subprocess.run(
                gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
            )

            if gs_process.returncode != 0:
                raise RuntimeError(
                    f"Error to compress file: {gs_process.stderr.decode('utf-8', 'ignore')}"
                )

            qpdf_cmd = [
                "qpdf",
                "--stream-data=compress",
                "--object-streams=generate",
                "--compress-streams=y",
                "--compression-level=9",
                output_path,
                output_compress_path,
            ]
            qpdf_process = subprocess.run(
                qpdf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
            )

            if qpdf_process.returncode != 0:
                raise RuntimeError(
                    f"Error to compress file: {qpdf_process.stderr.decode('utf-8', 'ignore')}"
                )

            with open(output_compress_path, "rb") as file:
                return file.read()

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Compression timeout: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {str(e)}")
        finally:
            for file_path in (input_path, output_path, output_compress_path):
                if file_path and path.exists(file_path):
                    try:
                        unlink(file_path)
                    except Exception:
                        pass

    def merge_pdf(self, bytes_list: List[bytes]):
        input_paths = []
        output_path = None

        try:
            for i, pdf_bytes in enumerate(bytes_list):
                with tempfile.NamedTemporaryFile(
                    suffix=f"_{i}.pdf", delete=False
                ) as input_file:
                    input_file.write(pdf_bytes)
                    input_paths.append(input_file.name)

            with tempfile.NamedTemporaryFile(
                suffix="_gs.pdf", delete=False
            ) as output_file:
                output_path = output_file.name

            qpdf_cmd = [
                "qpdf",
                "--linearize",
                "--empty",
                "--pages",
                *input_paths,
                "--",
                output_path,
                "--object-streams=generate",
                "--compress-streams=y",
                "--recompress-flate",
            ]
            qpdf_process = subprocess.run(
                qpdf_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
            )

            if qpdf_process.returncode != 0:
                raise RuntimeError(
                    f"Error merging PDFs: {qpdf_process.stderr.decode('utf-8', 'ignore')}"
                )

            with open(output_path, "rb") as merged:
                return merged.read()

        except subprocess.TimeoutExpired:
            raise RuntimeError("Merge operation timed out")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during merge: {str(e)}")
        finally:
            for p in input_paths + ([output_path] if output_path else []):
                if p and path.exists(p):
                    try:
                        unlink(p)
                    except Exception:
                        pass
