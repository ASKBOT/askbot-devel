"""hasher function that will calculate sha1 hash
directory contents
"""
import hashlib, os
import logging

def get_hash_of_dirs(dirs):
    """Hasher function for a directory and its files"""
    sha_hash = hashlib.sha1()
    for directory in dirs:
        if not os.path.exists (directory):
            return -1

        try:
            for root, dirs, files in os.walk(directory):
                for names in files:
                    filepath = os.path.join(root, names)
                    try:
                        file_obj = open(filepath, 'rb')
                    except Exception, error:
                        # You can't open the file for some reason
                        logging.critical(
                            'cannot open file %s: %s',
                            filepath,
                            error
                        )
                        file_obj.close()
                        continue

                    while 1:
                        # Read file in as little chunks
                        buf = file_obj.read(4096)
                        if not buf : break
                        sha_hash.update(hashlib.sha1(buf).hexdigest())
                    file_obj.close()

        except Exception:
            import traceback
            # Print the stack traceback
            traceback.print_exc()
            return -2

    return sha_hash.hexdigest()
