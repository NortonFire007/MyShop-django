import redis
from django.conf import settings
from .models import Product

r = redis.Redis(host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB)


class Recommender:
    @staticmethod
    def get_product_key(id):
        return f'product:{id}:purchased_with'

    def products_bought(self, products):
        product_ids = [product.id for product in products]
        product_relations = {}

        for product_id in product_ids:
            related_ids = [with_id for with_id in product_ids if with_id != product_id]
            key = self.get_product_key(product_id)
            if key not in product_relations:
                product_relations[key] = {}
            for with_id in related_ids:
                product_relations[key][with_id] = product_relations[key].get(with_id, 0) + 1

        for key, increments in product_relations.items():
            for with_id, score in increments.items():
                r.zincrby(key, score, with_id)

    def suggest_products_for(self, products, max_results=6):
        product_ids = [p.id for p in products]
        if len(products) == 1:
            suggestions = r.zrange(
                self.get_product_key(product_ids[0]),
                0, -1, desc=True)[:max_results]
        else:
            flat_ids = ''.join([str(id) for id in product_ids])
            tmp_key = f'tmp_{flat_ids}'
            keys = [self.get_product_key(id) for id in product_ids]
            r.zunionstore(tmp_key, keys)
            r.zrem(tmp_key, *product_ids)
            suggestions = r.zrange(tmp_key, 0, -1,
                                   desc=True)[:max_results]
            r.delete(tmp_key)

        suggested_products_ids = [int(id) for id in suggestions]
        suggested_products = list(Product.objects.filter(id__in=suggested_products_ids))
        suggested_products.sort(key=lambda x: suggested_products_ids.index(x.id))
        return suggested_products

    def clear_purchases(self):
        for id in Product.objects.values_list('id', flat=True):
            r.delete(self.get_product_key(id))
