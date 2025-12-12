"""
Phase 1, Step 2: Unified Schema Transformation with Walmart Support

Product Matching Project - Transform multi-source data to unified schema

This script transforms product data from Amazon, BestBuy, Target, and Walmart
into a universal unified schema.

Updated: 2025-12-12
Sources: 4 (Amazon, BestBuy, Target, Walmart)
Schema: See schema_config.yaml
"""

import json
import html
import csv
from datetime import datetime

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_brand(brand_str):
    """Normalize brand name to lowercase, remove suffixes"""
    if not brand_str:
        return None
    brand = str(brand_str).strip().lower()
    for suffix in [' inc.', ' inc', ' corp.', ' corp', ' llc', ' ltd', ' electronics']:
        brand = brand.replace(suffix, '')
    return brand.strip()

def parse_price(price_value):
    """Parse price string/float to float"""
    if price_value is None:
        return None
    if isinstance(price_value, (int, float)):
        return float(price_value)
    if isinstance(price_value, str):
        cleaned = price_value.replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned)
        except:
            return None
    return None

def extract_model_from_details(product_details):
    """Extract model number from Amazon product_details"""
    if not product_details or not isinstance(product_details, list):
        return None
    for detail in product_details:
        if isinstance(detail, dict) and 'model' in detail.get('type', '').lower():
            model = detail.get('value')
            if model:
                return str(model).strip().upper()
    return None

def extract_upc_from_details(product_details):
    """Extract UPC from Amazon product_details"""
    if not product_details or not isinstance(product_details, list):
        return None
    for detail in product_details:
        if isinstance(detail, dict) and detail.get('type') == 'UPC':
            upc = detail.get('value')
            if upc:
                return str(upc).replace('.0', '').strip()
    return None

def extract_brand_from_specs(specs):
    """Extract brand from BestBuy product_specifications"""
    if not specs or not isinstance(specs, list):
        return None
    for spec in specs:
        if isinstance(spec, dict) and spec.get('specification_name') == 'Brand':
            return spec.get('specification_value')
    return None

def extract_model_from_specs(specs):
    """Extract model from product specifications"""
    if not specs or not isinstance(specs, list):
        return None
    for spec in specs:
        if isinstance(spec, dict) and 'model' in spec.get('specification_name', '').lower():
            model = spec.get('specification_value')
            if model:
                return str(model).strip().upper()
    return None

def specs_to_dict(specs_array):
    """Convert specifications array to key-value dict"""
    if not specs_array or not isinstance(specs_array, list):
        return {}
    result = {}
    for spec in specs_array:
        if isinstance(spec, dict):
            name = spec.get('specification_name') or spec.get('name') or spec.get('type')
            value = spec.get('specification_value') or spec.get('value')
            if name and value:
                result[name] = value
    return result

def normalize_availability(availability_str):
    """Normalize availability to enum values"""
    if not availability_str:
        return None
    avail_lower = str(availability_str).lower()
    if any(word in avail_lower for word in ['in stock', 'available', 'add to cart', 'buy now']):
        return 'in_stock'
    elif any(word in avail_lower for word in ['out of stock', 'unavailable', 'sold out']):
        return 'out_of_stock'
    elif any(word in avail_lower for word in ['limited', 'few left', 'low stock']):
        return 'limited_stock'
    elif 'preorder' in avail_lower or 'pre-order' in avail_lower:
        return 'preorder'
    return 'in_stock'

def extract_category_path(breadcrumbs):
    """Safely extract category path from breadcrumbs"""
    if not breadcrumbs or not isinstance(breadcrumbs, list):
        return None
    categories = []
    for item in breadcrumbs:
        if isinstance(item, str):
            categories.append(item)
        elif isinstance(item, dict):
            name = item.get('name') or item.get('title') or item.get('category') or item.get('text')
            if name:
                categories.append(str(name))
    return ' > '.join(categories) if categories else None

def extract_primary_category(breadcrumbs):
    """Extract first category"""
    if not breadcrumbs or not isinstance(breadcrumbs, list) or len(breadcrumbs) == 0:
        return None
    first = breadcrumbs[0]
    if isinstance(first, str):
        return first
    elif isinstance(first, dict):
        return first.get('name') or first.get('title') or first.get('category') or first.get('text')
    return None

# ============================================================================
# WALMART-SPECIFIC HELPER FUNCTIONS
# ============================================================================

def extract_walmart_seller(seller_info):
    """Extract seller name from Walmart seller_info array"""
    if not seller_info or not isinstance(seller_info, list):
        return "Walmart"
    if len(seller_info) > 0 and isinstance(seller_info[0], dict):
        seller_name = seller_info[0].get('seller_name')
        if seller_name:
            return str(seller_name).strip()
    return "Walmart"

def transform_walmart_rating_stars(rating_stars):
    """Transform Walmart rating_stars to standardized format"""
    if not rating_stars or not isinstance(rating_stars, dict):
        return None

    # Walmart format: {"one_star": 3, "two_stars": 2, "three_stars": 6, ...}
    # Convert to: {"1": 3, "2": 2, "3": 6, ...}
    standardized = {}

    mapping = {
        'one_star': '1',
        'two_stars': '2', 
        'three_stars': '3',
        'four_stars': '4',
        'five_stars': '5'
    }

    for key, value in rating_stars.items():
        if key in mapping:
            standardized[mapping[key]] = value

    return standardized if standardized else None

def extract_walmart_customer_sentiment(top_reviews):
    """Extract customer sentiment from Walmart top_reviews"""
    if not top_reviews or not isinstance(top_reviews, dict):
        return None

    sentiment_parts = []

    if 'positive' in top_reviews and isinstance(top_reviews['positive'], dict):
        pos_review = top_reviews['positive'].get('review')
        if pos_review:
            sentiment_parts.append(f"Positive: {pos_review[:200]}")

    if 'negative' in top_reviews and isinstance(top_reviews['negative'], dict):
        neg_review = top_reviews['negative'].get('review')
        if neg_review:
            sentiment_parts.append(f"Negative: {neg_review[:200]}")

    return ' | '.join(sentiment_parts) if sentiment_parts else None

# ============================================================================
# TRANSFORMATION FUNCTIONS
# ============================================================================

def transform_amazon_to_unified(amazon_record):
    """Transform Amazon record to unified schema"""
    categories = amazon_record.get('categories')
    cat_list = categories if isinstance(categories, list) else []

    unified = {
        "source_product_id": amazon_record.get('asin'),
        "source_parent_id": amazon_record.get('parent_asin'),
        "upc": extract_upc_from_details(amazon_record.get('product_details')),
        "model_number": extract_model_from_details(amazon_record.get('product_details')),
        "title": amazon_record.get('title', '').strip() if amazon_record.get('title') else None,
        "brand_name": normalize_brand(amazon_record.get('brand')),
        "description": amazon_record.get('description'),
        "current_price": parse_price(amazon_record.get('final_price')),
        "original_price": parse_price(amazon_record.get('initial_price')),
        "discount_amount": None,
        "discount_percentage": None,
        "currency": amazon_record.get('currency', 'USD'),
        "rating": amazon_record.get('rating'),
        "reviews_count": amazon_record.get('reviews_count'),
        "rating_distribution": amazon_record.get('amount_of_stars'),
        "customer_sentiment": amazon_record.get('customer_says'),
        "images": amazon_record.get('images'),
        "videos": amazon_record.get('videos'),
        "primary_image": amazon_record.get('images', [None])[0] if amazon_record.get('images') else None,
        "specifications": specs_to_dict(amazon_record.get('product_details')),
        "features": amazon_record.get('features'),
        "highlights": None,
        "category_path": ' > '.join(cat_list) if cat_list else None,
        "primary_category": cat_list[0] if len(cat_list) > 0 else None,
        "secondary_category": cat_list[1] if len(cat_list) > 1 else None,
        "tertiary_category": cat_list[2] if len(cat_list) > 2 else None,
        "availability_status": normalize_availability(amazon_record.get('availability')),
        "delivery_info": amazon_record.get('delivery'),
        "seller_name": amazon_record.get('seller_name'),
        "has_variants": bool(amazon_record.get('variations')),
        "variant_attributes": None,
        "variant_value": None,
        "variant_group_id": amazon_record.get('parent_asin'),
        "seller_id": amazon_record.get('seller_id'),
        "seller_rating": amazon_record.get('seller_rating'),
        "source": "amazon",
        "source_url": amazon_record.get('url'),
        "scraped_at": amazon_record.get('timestamp'),
        "last_updated": None,
        "badges": [amazon_record.get('badge')] if amazon_record.get('badge') else [],
        "is_sponsored": bool(amazon_record.get('sponsored')),
        "is_prime": bool(amazon_record.get('amazon_prime')),
        "special_offers": None
    }

    if unified['current_price'] and unified['original_price']:
        unified['discount_amount'] = unified['original_price'] - unified['current_price']
        if unified['original_price'] > 0:
            unified['discount_percentage'] = (unified['discount_amount'] / unified['original_price']) * 100

    return unified

def transform_bestbuy_to_unified(bestbuy_record):
    """Transform BestBuy record to unified schema"""
    breadcrumbs = bestbuy_record.get('breadcrumbs')

    unified = {
        "source_product_id": str(bestbuy_record.get('sku', '')).replace('.0', ''),
        "source_parent_id": None,
        "upc": str(bestbuy_record.get('upc', '')).replace('.0', '') if bestbuy_record.get('upc') else None,
        "model_number": bestbuy_record.get('model', '').strip().upper() if bestbuy_record.get('model') else None,
        "title": bestbuy_record.get('title', '').strip() if bestbuy_record.get('title') else None,
        "brand_name": normalize_brand(extract_brand_from_specs(bestbuy_record.get('product_specifications'))),
        "description": bestbuy_record.get('product_description'),
        "current_price": parse_price(bestbuy_record.get('final_price')),
        "original_price": parse_price(bestbuy_record.get('initial_price')),
        "discount_amount": None,
        "discount_percentage": None,
        "currency": bestbuy_record.get('currency', 'USD'),
        "rating": bestbuy_record.get('rating'),
        "reviews_count": bestbuy_record.get('reviews_count'),
        "rating_distribution": bestbuy_record.get('amount_of_stars'),
        "customer_sentiment": None,
        "images": bestbuy_record.get('images'),
        "videos": None,
        "primary_image": bestbuy_record.get('images', [None])[0] if bestbuy_record.get('images') else None,
        "specifications": specs_to_dict(bestbuy_record.get('product_specifications')),
        "features": bestbuy_record.get('features'),
        "highlights": bestbuy_record.get('highlights'),
        "category_path": extract_category_path(breadcrumbs),
        "primary_category": extract_primary_category(breadcrumbs),
        "secondary_category": None,
        "tertiary_category": None,
        "availability_status": normalize_availability(bestbuy_record.get('availability')),
        "delivery_info": None,
        "seller_name": "BestBuy",
        "has_variants": bool(bestbuy_record.get('variations')),
        "variant_attributes": None,
        "variant_value": None,
        "variant_group_id": None,
        "seller_id": None,
        "seller_rating": None,
        "source": "bestbuy",
        "source_url": bestbuy_record.get('url'),
        "scraped_at": bestbuy_record.get('timestamp'),
        "last_updated": None,
        "badges": [],
        "is_sponsored": False,
        "is_prime": False,
        "special_offers": None
    }

    if unified['current_price'] and unified['original_price']:
        unified['discount_amount'] = unified['original_price'] - unified['current_price']
        if unified['original_price'] > 0:
            unified['discount_percentage'] = (unified['discount_amount'] / unified['original_price']) * 100

    return unified

def transform_target_to_unified(target_record):
    """Transform Target record to unified schema"""
    breadcrumbs = target_record.get('breadcrumbs')

    unified = {
        "source_product_id": str(target_record.get('tcin_id', '')).replace('.0', ''),
        "source_parent_id": None,
        "upc": str(target_record.get('upc', '')).replace('.0', '') if target_record.get('upc') else None,
        "model_number": extract_model_from_specs(target_record.get('product_specifications')),
        "title": html.unescape(target_record.get('title', '').strip()) if target_record.get('title') else None,
        "brand_name": normalize_brand(target_record.get('product_brand')),
        "description": html.unescape(target_record.get('product_description', '')) if target_record.get('product_description') else None,
        "current_price": parse_price(target_record.get('final_price')),
        "original_price": parse_price(target_record.get('initial_price')),
        "discount_amount": None,
        "discount_percentage": parse_price(target_record.get('discount')),
        "currency": target_record.get('currency', 'USD'),
        "rating": target_record.get('rating'),
        "reviews_count": target_record.get('reviews_count'),
        "rating_distribution": target_record.get('amount_of_stars'),
        "customer_sentiment": target_record.get('what_customers_said'),
        "images": target_record.get('images'),
        "videos": None,
        "primary_image": target_record.get('images', [None])[0] if target_record.get('images') else None,
        "specifications": specs_to_dict(target_record.get('product_specifications')),
        "features": None,
        "highlights": None,
        "category_path": extract_category_path(breadcrumbs),
        "primary_category": extract_primary_category(breadcrumbs),
        "secondary_category": None,
        "tertiary_category": None,
        "availability_status": normalize_availability(target_record.get('availability_text')),
        "delivery_info": None,
        "seller_name": target_record.get('seller_name', 'Target'),
        "has_variants": bool(target_record.get('variations')),
        "variant_attributes": None,
        "variant_value": None,
        "variant_group_id": None,
        "seller_id": None,
        "seller_rating": None,
        "source": "target",
        "source_url": target_record.get('url'),
        "scraped_at": target_record.get('timestamp'),
        "last_updated": None,
        "badges": [],
        "is_sponsored": False,
        "is_prime": False,
        "special_offers": None
    }

    if unified['current_price'] and unified['original_price']:
        unified['discount_amount'] = unified['original_price'] - unified['current_price']
        if not unified['discount_percentage'] and unified['original_price'] > 0:
            unified['discount_percentage'] = (unified['discount_amount'] / unified['original_price']) * 100

    return unified

def transform_walmart_to_unified(walmart_record):
    """Transform Walmart record to unified schema"""
    breadcrumbs = walmart_record.get('breadcrumbs')

    # Handle title - may need HTML decoding
    title = walmart_record.get('title')
    if title:
        title = html.unescape(str(title).strip())

    # Handle description - may have HTML
    description = walmart_record.get('description')
    if description:
        description = html.unescape(str(description))

    # Handle store info for delivery_info
    delivery_info_parts = []
    if walmart_record.get('store_name'):
        delivery_info_parts.append(f"Store: {walmart_record.get('store_name')}")
    if walmart_record.get('store_location'):
        delivery_info_parts.append(f"Location: {walmart_record.get('store_location')}")
    delivery_info = ', '.join(delivery_info_parts) if delivery_info_parts else None

    unified = {
        "source_product_id": str(walmart_record.get('product_id', '')).replace('.0', ''),
        "source_parent_id": None,
        "upc": str(walmart_record.get('upc', '')).replace('.0', '') if walmart_record.get('upc') else None,
        "model_number": extract_model_from_specs(walmart_record.get('specifications')),
        "title": title,
        "brand_name": normalize_brand(walmart_record.get('brand')),
        "description": description,
        "current_price": parse_price(walmart_record.get('final_price')),
        "original_price": parse_price(walmart_record.get('initial_price')),
        "discount_amount": parse_price(walmart_record.get('discount')),
        "discount_percentage": None,
        "currency": walmart_record.get('currency', 'USD'),
        "rating": walmart_record.get('rating') or walmart_record.get('rating_count'),
        "reviews_count": walmart_record.get('reviews_count') or walmart_record.get('review_count'),
        "rating_distribution": transform_walmart_rating_stars(walmart_record.get('rating_stars')),
        "customer_sentiment": extract_walmart_customer_sentiment(walmart_record.get('top_reviews')),
        "images": walmart_record.get('image_urls') or walmart_record.get('images'),
        "videos": walmart_record.get('videos'),
        "primary_image": (walmart_record.get('image_urls') or walmart_record.get('images') or [None])[0],
        "specifications": specs_to_dict(walmart_record.get('specifications')),
        "features": None,
        "highlights": None,
        "category_path": extract_category_path(breadcrumbs),
        "primary_category": walmart_record.get('category_name') or extract_primary_category(breadcrumbs),
        "secondary_category": None,
        "tertiary_category": None,
        "availability_status": normalize_availability(walmart_record.get('availability_text')),
        "delivery_info": delivery_info,
        "seller_name": extract_walmart_seller(walmart_record.get('seller_info')),
        "has_variants": bool(walmart_record.get('variants')),
        "variant_attributes": None,
        "variant_value": None,
        "variant_group_id": None,
        "seller_id": None,
        "seller_rating": None,
        "source": "walmart",
        "source_url": walmart_record.get('url'),
        "scraped_at": None,
        "last_updated": None,
        "badges": [],
        "is_sponsored": False,
        "is_prime": False,
        "special_offers": walmart_record.get('promotion_fulltext')
    }

    # Calculate discount percentage if not available
    if unified['current_price'] and unified['original_price']:
        if not unified['discount_amount']:
            unified['discount_amount'] = unified['original_price'] - unified['current_price']
        if unified['original_price'] > 0:
            unified['discount_percentage'] = (unified['discount_amount'] / unified['original_price']) * 100

    return unified

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("UNIFIED SCHEMA TRANSFORMATION (4 SOURCES)")
    print("="*80)

    # Load data
    def load_ndjson(filename):
        data = []
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line))
        return data

    print("\nLoading source data...")
    amazon_data = load_ndjson('amazon_final.json')
    bestbuy_data = load_ndjson('bestbuy_final.json')
    target_data = load_ndjson('target_final.json')
    walmart_data = load_ndjson('walmart_final.json')

    print(f"✓ Loaded {len(amazon_data)} Amazon records")
    print(f"✓ Loaded {len(bestbuy_data)} BestBuy records")
    print(f"✓ Loaded {len(target_data)} Target records")
    print(f"✓ Loaded {len(walmart_data)} Walmart records")

    # Transform all records
    print("\nTransforming to unified schema...")
    unified_amazon = [transform_amazon_to_unified(rec) for rec in amazon_data]
    unified_bestbuy = [transform_bestbuy_to_unified(rec) for rec in bestbuy_data]
    unified_target = [transform_target_to_unified(rec) for rec in target_data]
    unified_walmart = [transform_walmart_to_unified(rec) for rec in walmart_data]

    print(f"✓ Transformed {len(unified_amazon)} Amazon records")
    print(f"✓ Transformed {len(unified_bestbuy)} BestBuy records")
    print(f"✓ Transformed {len(unified_target)} Target records")
    print(f"✓ Transformed {len(unified_walmart)} Walmart records")

    # Combine and export
    all_unified = unified_amazon + unified_bestbuy + unified_target + unified_walmart

    with open('unified_products.json', 'w', encoding='utf-8') as f:
        for record in all_unified:
            f.write(json.dumps(record) + '\n')

    print(f"\n✓ Exported {len(all_unified)} unified records to: unified_products.json")

    # Summary by source
    print("\n" + "="*80)
    print("TRANSFORMATION SUMMARY")
    print("="*80)

    from collections import Counter
    source_counts = Counter([r['source'] for r in all_unified])

    print("\nRecords by source:")
    for source, count in sorted(source_counts.items()):
        pct = (count / len(all_unified)) * 100
        print(f"  {source:10} : {count:>5} records ({pct:>5.1f}%)")

    print(f"\n  TOTAL      : {len(all_unified):>5} records")

    print("\n" + "="*80)
    print("TRANSFORMATION COMPLETE")
    print("="*80)
