"""Plain-text Vietnamese templates for the notification outbox."""

def order_confirmation(order_id: str, total: int, payment: str) -> tuple[str, str]:
    return (
        "ReLoop Market · Xác nhận đơn hàng",
        f"Đơn hàng {order_id} đã được tạo thành công.\nTổng thanh toán: {total:,}đ.\nPhương thức thanh toán: {payment}.\n\nĐây là thông báo tự động từ ReLoop Market.",
    )


def order_status(order_id: str, status: str) -> tuple[str, str]:
    return (
        "ReLoop Market · Cập nhật đơn hàng",
        f"Đơn hàng {order_id} đã chuyển sang trạng thái: {status}.\n\nĐây là thông báo tự động từ ReLoop Market.",
    )
