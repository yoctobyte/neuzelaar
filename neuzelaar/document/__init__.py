"""Internal document tree, subresource, style, and layout models.

This layer owns the internal representation of the page. It is populated by 
engine adapters and consumed by renderers. It must not contain third-party 
library objects (like html5lib nodes).
"""
