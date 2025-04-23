# Changelog: Update FileIO Dependencies

**Date:** 04-22-2025

## Summary

Updated the version constraints for dependencies listed under the `fileio` extra in `setup.py`.

## Justification

The previous version constraints for `boto3`, `botocore`, `aiobotocore`, `s3fs`, `fsspec`, and `s3transfer` were outdated. Specifically, `urllib3` was unnecessarily pinned below version 2. This update brings the dependencies to more recent, compatible versions, leveraging the synchronized versioning of `boto3` and `botocore` (since v1.33.0) and removing outdated restrictions. This allows users to benefit from newer features and security patches in these libraries.

## Usage Examples

N/A

## Dependency Changes

The following dependencies under the `fileio` extra in `setup.py` were updated:

*   `botocore`: Updated from `==1.29.76` to `>=1.34.0`
*   `urllib3`: Constraint `< 2` removed.
*   `aiobotocore`: Updated from `==2.5.0` to `>=2.11.0`
*   `s3fs`: Updated from `==2023.6.0` to `>=2024.2.0`
*   `boto3`: Updated from `==1.26.76` to `>=1.34.0`
*   `fsspec`: Updated from `==2023.6.0` to `>=2024.2.0`
*   `s3transfer`: Updated from `==0.6.1` to `>=0.10.0`
*   `python-magic`, `aiopath`, `aiofiles`, `aiofile`: Constraints remain unspecified (allowing latest).

## Breaking Changes

None anticipated. This change primarily loosens constraints to allow newer versions. 