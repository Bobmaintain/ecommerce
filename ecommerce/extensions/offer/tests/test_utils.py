from decimal import Decimal

import ddt
import mock
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.checkout.utils import add_currency
from ecommerce.extensions.offer.utils import (
    _remove_exponent_and_trailing_zeros,
    format_benefit_value,
    send_assigned_offer_email
)
from ecommerce.extensions.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class UtilTests(DiscoveryTestMixin, TestCase):

    def setUp(self):
        super(UtilTests, self).setUp()
        self.course = CourseFactory(partner=self.partner)
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100)
        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price_excl_tax
        self._range = RangeFactory(products=[self.verified_seat, ])

        self.percentage_benefit = BenefitFactory(type=Benefit.PERCENTAGE, range=self._range, value=35.00)
        self.value_benefit = BenefitFactory(type=Benefit.FIXED, range=self._range, value=self.seat_price - 10)

    def test_format_benefit_value(self):
        """ format_benefit_value(benefit) should format benefit value based on benefit type """
        benefit_value = format_benefit_value(self.percentage_benefit)
        self.assertEqual(benefit_value, '35%')

        benefit_value = format_benefit_value(self.value_benefit)
        expected_benefit = add_currency(Decimal((self.seat_price - 10)))
        self.assertEqual(benefit_value, '${expected_benefit}'.format(expected_benefit=expected_benefit))

    def test_format_program_benefit_value(self):
        """ format_benefit_value(program_benefit) should format benefit value based on proxy class. """
        percentage_benefit = PercentageDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(percentage_benefit)
        self.assertEqual(benefit_value, '{}%'.format(percentage_benefit.value))

        absolute_benefit = AbsoluteDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(absolute_benefit)
        expected_value = add_currency(Decimal(absolute_benefit.value))
        self.assertEqual(benefit_value, '${}'.format(expected_value))

    @ddt.data(
        ('1.0', '1'),
        ('5000.0', '5000'),
        ('1.45000', '1.45'),
        ('5000.40000', '5000.4'),
    )
    @ddt.unpack
    def test_remove_exponent_and_trailing_zeros(self, value, expected):
        """
        _remove_exponent_and_trailing_zeros(decimal) should remove exponent and trailing zeros
        from decimal number
        """
        decimal = _remove_exponent_and_trailing_zeros(Decimal(value))
        self.assertEqual(decimal, Decimal(expected))

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_assignment_email')
    @ddt.data(
        (
            ('Your learning manager has provided you with a new access code to take a course at edX.'
             ' You may redeem this code for {code_usage_count} courses. '

             'edX login: {user_email}'
             'Enrollment url: {enrollment_url}'
             'Access Code: {code}'
             'Expiration date: {code_expiration_date}'

             'You may go directly to the Enrollment URL to view courses that are available for this code'
             ' or you can insert the access code at check out under "coupon code" for applicable courses.'

             'For any questions, please reach out to your Learning Manager.'),
            {'offer_assignment_id': 555,
             'learner_email': 'johndoe@unknown.com',
             'code': 'GIL7RUEOU7VHBH7Q',
             'enrollment_url': 'http://tempurl.url/enroll',
             'code_usage_count': 10,
             'code_expiration_date': '2018-12-19'},
            ('Your learning manager has provided you with a new access code to take a course at edX.'
             ' You may redeem this code for 10 courses. '

             'edX login: johndoe@unknown.com'
             'Enrollment url: http://tempurl.url/enroll'
             'Access Code: GIL7RUEOU7VHBH7Q'
             'Expiration date: 2018-12-19'

             'You may go directly to the Enrollment URL to view courses that are available for this code'
             ' or you can insert the access code at check out under "coupon code" for applicable courses.'

             'For any questions, please reach out to your Learning Manager.'),
            None,
            True,
        ),
        (
            ('Your learning manager has provided you with a new access code to take a course at edX.'
             ' You may redeem this code for {code_usage_count} courses. '

             'edX login: {user_email}'
             'Enrollment url: {enrollment_url}'
             'Access Code: {code}'
             'Expiration date: {code_expiration_date}'

             'You may go directly to the Enrollment URL to view courses that are available for this code'
             ' or you can insert the access code at check out under "coupon code" for applicable courses.'

             'For any questions, please reach out to your Learning Manager.'),
            {'offer_assignment_id': 555,
             'learner_email': 'johndoe@unknown.com',
             'code': 'GIL7RUEOU7VHBH7Q',
             'enrollment_url': 'http://tempurl.url/enroll',
             'code_usage_count': 10,
             'code_expiration_date': '2018-12-19'},
            ('Your learning manager has provided you with a new access code to take a course at edX.'
             ' You may redeem this code for 10 courses. '

             'edX login: johndoe@unknown.com'
             'Enrollment url: http://tempurl.url/enroll'
             'Access Code: GIL7RUEOU7VHBH7Q'
             'Expiration date: 2018-12-19'

             'You may go directly to the Enrollment URL to view courses that are available for this code'
             ' or you can insert the access code at check out under "coupon code" for applicable courses.'

             'For any questions, please reach out to your Learning Manager.'),
            Exception(),
            False,
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_email(
            self,
            template,
            tokens,
            expected_email_body,
            side_effect,
            returns,
            mock_sailthru_task,
    ):
        email_subject = 'New edX course assignment'
        mock_sailthru_task.delay.side_effect = side_effect
        status = send_assigned_offer_email(
            template,
            tokens.get('offer_assignment_id'),
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('enrollment_url'),
            tokens.get('code_usage_count'),
            tokens.get('code_expiration_date'),
        )
        mock_sailthru_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            tokens.get('offer_assignment_id'),
            email_subject, expected_email_body)
        self.assertEqual(status, returns)
