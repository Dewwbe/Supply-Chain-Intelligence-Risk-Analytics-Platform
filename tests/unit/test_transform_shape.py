import pandas as pd
from etl.transform import dataco_transform, olist_transform


def _olist_fixture() -> dict[str, pd.DataFrame]:
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "customer_id": ["c1", "c2"],
            "order_status": ["delivered", "canceled"],
            "order_purchase_timestamp": ["2018-01-01", "2018-01-02"],
            "order_approved_at": ["2018-01-01", "2018-01-02"],
            "order_delivered_carrier_date": ["2018-01-02", None],
            "order_delivered_customer_date": ["2018-01-05", None],
            "order_estimated_delivery_date": ["2018-01-10", "2018-01-12"],
        }
    )
    order_items = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "order_item_id": [1, 1],
            "product_id": ["p1", "p2"],
            "seller_id": ["s1", "s2"],
            "shipping_limit_date": ["2018-01-03", "2018-01-04"],
            "price": [100.0, 50.0],
            "freight_value": [10.0, 5.0],
        }
    )
    products = pd.DataFrame(
        {
            "product_id": ["p1", "p2"],
            "product_category_name": ["cama_mesa_banho", "eletronicos"],
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": ["c1", "c2"],
            "customer_city": ["sao paulo", "rio de janeiro"],
            "customer_state": ["SP", "RJ"],
        }
    )
    category_translation = pd.DataFrame(
        {
            "product_category_name": ["cama_mesa_banho"],
            "product_category_name_english": ["bed_bath_table"],
        }
    )
    return {
        "orders": orders,
        "order_items": order_items,
        "products": products,
        "customers": customers,
        "category_translation": category_translation,
    }


def _dataco_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Order Id": [1001],
            "Order Item Id": [5001],
            "order date (DateOrders)": ["2018-01-01"],
            "shipping date (DateOrders)": ["2018-01-04"],
            "Order Customer Id": [42],
            "Customer Segment": ["Consumer"],
            "Product Card Id": [777],
            "Product Name": ["Trail Running Shoe"],
            "Category Name": ["Cleats"],
            "Order Item Quantity": [2],
            "Order Item Product Price": [40.0],
            "Sales": [80.0],
            "Order Item Discount": [8.0],
            "Order Region": ["Southeast Asia"],
            "Order Status": ["COMPLETE"],
            "Delivery Status": ["Shipping on time"],
            "Shipping Mode": ["Standard Class"],
            "Days for shipment (scheduled)": [4],
            "Days for shipping (real)": [3],
            "Department Name": ["Fitness"],
        }
    )


def test_olist_and_dataco_produce_the_same_shape():
    fixtures = _olist_fixture()
    olist_lines = olist_transform.build_sales_lines(**fixtures)
    dataco_lines = dataco_transform.build_sales_lines(_dataco_fixture())

    assert list(olist_lines.columns) == olist_transform.SALES_LINE_COLUMNS
    assert list(dataco_lines.columns) == olist_transform.SALES_LINE_COLUMNS


def test_olist_quantity_is_always_one_line_item_per_row():
    fixtures = _olist_fixture()
    olist_lines = olist_transform.build_sales_lines(**fixtures)
    assert (olist_lines["quantity"] == 1).all()


def test_olist_cancelled_order_gets_shipping_cancelled_status():
    fixtures = _olist_fixture()
    olist_lines = olist_transform.build_sales_lines(**fixtures)
    cancelled_row = olist_lines[olist_lines["order_id"] == "o2"].iloc[0]
    assert cancelled_row["order_status"] == "Cancelled"
    assert cancelled_row["delivery_status"] == "Shipping Cancelled"


def test_dataco_currency_conversion_and_department_passthrough():
    dataco_lines = dataco_transform.build_sales_lines(_dataco_fixture())
    row = dataco_lines.iloc[0]
    assert row["original_currency"] == "USD"
    assert row["sales_amount_aed"] == 80.0 * 3.6725
    assert row["source_department"] == "Fitness"
    assert row["emirate"] in {"Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah"}
    assert row["discount_amount_aed"] == 8.0 * 3.6725


def test_olist_has_no_discount_data():
    fixtures = _olist_fixture()
    olist_lines = olist_transform.build_sales_lines(**fixtures)
    assert (olist_lines["discount_amount_aed"] == 0.0).all()
