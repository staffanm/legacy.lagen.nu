from DocumentRepository import DocumentRepository

class W3Standards(DocumentRepository):
    module_dir = "w3rec"
    start_url = "http://www.w3.org/TR/tr-date-stds"

    # This results in fairly long basenames like "2010/REC-xhtml11-20101123"
    document_url = "http://www.w3.org/TR/%s/"



