# -*- coding: utf-8 -*-

from django.test import TestCase
from booking.models import Booking, SystemAccount, UserProfile
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

class BookingModelTestCase(TestCase):

    def setUp(self):
        # Создание пользователей
        user1 = User.objects.create_user(
            'john', 'lennon@thebeatles.com', 'johnpassword'
        )
        user1.save()
        user2 = User.objects.create_user(
            'johndow', 'johndow@test.com', 'dowpassword'
        )
        user2.save()
        Booking.objects.create(
            title="test_booking",
            text="test_booking_text",
            price=150,
            customer=user1
        )
        SystemAccount.objects.create()
        UserProfile.objects.create(user=user1)
        UserProfile.objects.create(user=user2)

    def test_booking_processing(self):
        """
        Создание двух пользователей: исполнитель и заказчик.
        Создание заказа.
        Назначение заказу заказчика.
        Назначание заказу исполнителя.
        Исполнение заказа.
        Проверка статусов заказа в ходе этих назначений.
        Проверка назначенности заказу пользователей в ходе этих назначений.
        """

        booking = Booking.objects.get(title='test_booking')

        self.assertEqual(booking.get_status(), Booking.PENDING)

        user1 = User.objects.get(username='john')
        booking.set_customer(user1)
        booking.save()

        self.assertEqual(booking.get_customer(), user1)

        user2 = User.objects.get(username='johndow')
        booking.set_performer(user2)
        booking.save()

        booking.set_status(Booking.RUNNING)
        booking.save()

        self.assertEqual(booking.get_status(), Booking.RUNNING)
        self.assertEqual(booking.get_performer(), user2)

        booking.complete()

        self.assertEqual(booking.get_status(), Booking.COMPLETED)


class BookingViewsTestCase(TestCase):

    def setUp(self):
        """
        Создание пользователей: заказчик, исполнитель.
        Назначение им прав на создание исполнение заказа соответсвенно.
        """
        user1 = User.objects.create_user(
            'john', 'lennon@thebeatles.com', 'johnpassword'
        )
        user1.save()
        user2 = User.objects.create_user(
            'johndow', 'johndow@test.com', 'dowpassword'
        )
        user2.save()
        SystemAccount.objects.create()
        UserProfile.objects.create(user=user1, cash=20.00)
        UserProfile.objects.create(user=user2, cash=0.00)

        content_type = ContentType.objects.get_for_model(Booking)
        permission = Permission.objects.create(
            content_type=content_type, codename='add_booking')
        user1.user_permissions.add(permission)
        user1.save()

        permission = Permission.objects.get(
            content_type=content_type, codename='perform_perm')
        user2.user_permissions.add(permission)
        user2.save()

        # Создание группы с правами
        booking_content = ContentType.objects.get_for_model(Booking)

        customers, is_created = Group.objects.get_or_create(name="customers")
        add = Permission.objects.create(
            name="Can add", codename="can_add", content_type=booking_content)
        change = Permission.objects.create(
            name="Can change", codename="can_change", content_type=booking_content)
        delete = Permission.objects.create(
            name="Can delete", codename="can_delete", content_type=booking_content)

        customers.permissions.add(add)
        customers.permissions.add(change)
        customers.permissions.add(delete)
        customers.save()

        self.assertEqual(len(customers.permissions.all()), 3)
        self.assertEqual(customers.permissions.all()[0], add)
        self.assertEqual(customers.permissions.all()[1], change)
        self.assertEqual(customers.permissions.all()[2], delete)

        # Назначение пользователю группы
        user1.groups.add(customers)
        user1.save()

        self.assertEqual(len(user1.groups.all()), 1)
        self.assertEqual(user1.groups.all()[0], customers)

        # Создание группы с правами
        performers, is_created = Group.objects.get_or_create(name="performers")
        perform = Permission.objects.create(name="Can perform",
                                            codename="perform", content_type=booking_content)

        performers.permissions.add(perform)
        performers.save()

        self.assertEqual(len(performers.permissions.all()), 1)
        self.assertEqual(performers.permissions.all()[0], perform)

        # Назначение пользоателю группы
        user2.groups.add(performers)
        user2.save()

        self.assertEqual(len(user2.groups.all()), 1)
        self.assertEqual(user2.groups.all()[0], performers)

    def test_calling_view_without_being_logged_in(self):
        response = self.client.get(reverse('create-booking'), follow=True)
        self.assertRedirects(
            response, '/accounts/login/?next=/booking/create_booking/')
        response = self.client.get(reverse('booking-list'), follow=True)
        self.assertRedirects(
            response, '/accounts/login/?next=/booking/booking_list/')
        response = self.client.get('/home/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'homepage.html')

    def test_create_customer_and_performer_create_booking_and_serve(self):
        """
        Заказчик создает заказ.
        Другой берет его на выполнение.
        Первый подтверждает и завершает заказ.
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Ждет подтверждения взятия на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user = User.objects.get(username='john')

        # Подтверждение исполнителем взятия заказа заказчиком
        response = self.client.post(reverse('approve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.RUNNING)
        self.assertEqual(user1.profile.cash + booking.price, user1_cash_before)

        # Закрытие заказа
        response = self.client.post(reverse('complete-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Завершен
        user2 = User.objects.get(username='johndow')
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.COMPLETED)
        system_account = SystemAccount.objects.all()[0]
        comission = system_account.get_comission()
        self.assertEqual(system_account.account, booking.price * comission)
        self.assertEqual(user2.profile.cash, booking.price * (1 - comission))

    def test_create_three_users_create_booking_and_2nd_customer_can_not_complete(self):
        """
        Создать трех пользователей - два заказчика и исполнитель.
        Первый заказчик создает заказ. Исполнитель подает заявку на обслуживание
        заказа. Первый подтверждает.
        Второй заказчик не должен смочь завершить заказ.
        """
        # Добавление третьего пользователя (заказчик)
        user3 = User.objects.create_user(
            'johnthird', 'johndow@test.com', 'thirdpassword'
        )
        user3.save()
        UserProfile.objects.create(user=user3, cash=0.00)
        content_type = ContentType.objects.get_for_model(Booking)
        permission = Permission.objects.get(
            content_type=content_type, codename='add_booking')
        user3.user_permissions.add(permission)
        user3.save()

        user1 = User.objects.get(username='john')
        user2 = User.objects.get(username='johndow')
        user1_cash_before = user1.profile.cash
        user2_cash_before = user2.profile.cash

        # Вход из-под 1го поьзователя
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Ждет подтверждения взятия исполнителем от заказчика (первого)
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика (первого)
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')


        # Подтверждение заказчиком взятия заказа
        response = self.client.post(reverse('approve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.RUNNING)
        self.assertEqual(user1.profile.cash + booking.price, user1_cash_before)


        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под второго заказчика
        response = self.client.post('/accounts/login/',
            {'username': 'johnthird', 'password': 'thirdpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Закрытие заказа
        response = self.client.post(reverse('complete-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # По прежнему взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.RUNNING)
        system_account = SystemAccount.objects.all()[0]
        comission = system_account.get_comission()
        self.assertEqual(system_account.account, 0.0)
        self.assertEqual(user3.profile.cash, 0.0)
        self.assertEqual(user2.profile.cash, user2_cash_before)

    def test_create_three_users_create_booking_and_2nd_customer_can_not_approve(self):
        """
        Создать трех пользователей - два заказчика и исполнитель.
        Первый заказчик создает заказ. Исполнитель подает заявку на обслуживание
        заказа.
        Второй заказчик не должен смочь подтвердить эту заявку.
        """
        # Добавление третьего пользователя (заказчик)
        user3 = User.objects.create_user(
            'johnthird', 'johndow@test.com', 'thirdpassword'
        )
        user3.save()
        UserProfile.objects.create(user=user3, cash=0.00)
        content_type = ContentType.objects.get_for_model(Booking)
        permission = Permission.objects.get(
            content_type=content_type, codename='add_booking')
        user3.user_permissions.add(permission)
        user3.save()

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash
        user2 = User.objects.get(username='johndow')
        user2_cash_before = user2.profile.cash

        # Вход из-под 1го поьзователя
        response = self.client.post('/accounts/login/',
            {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Ждет подтверждения взятия исполнителем от заказчика (первого)
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика (второго)
        response = self.client.post('/accounts/login/',
            {'username': 'johnthird', 'password': 'thirdpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')


        # Подтверждение заказчиком взятия заказа
        response = self.client.post(reverse('approve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # По-прежнему ждет подтверждения
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)
        self.assertEqual(user1.profile.cash, user1_cash_before)

    def test_performer_can_not_perform_booking_of_other_performer(self):
        """
        Создать двух пользователей - заказчик и заказчик. Один создает заказ.
        Второму не хватает прав для взятия на выполнение.
        """
        # Добавление третьего пользователя (заказчик)
        user3 = User.objects.create_user(
            'johnthird', 'johndow@test.com', 'thirdpassword'
        )
        user3.save()
        UserProfile.objects.create(user=user3, cash=0.00)

        content_type = ContentType.objects.get_for_model(Booking)
        permission = Permission.objects.get(
            content_type=content_type, codename='add_booking')
        user3.user_permissions.add(permission)
        user3.save()

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под второго заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'johnthird', 'password': 'thirdpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        #user3 = User.objects.get(username='johnthird')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Перенаправление на страницу логина означает отсутствие прав на view
        self.assertTemplateUsed(response, 'registration/login.html')


        # Попытка удаления заказа - удалить может только создававший
        response = self.client.post(reverse('delete-booking',
                             kwargs={'pk': booking.id }),
                             follow=True)
        self.assertEqual(response.status_code, 404)

        bookings = Booking.objects.all()
        self.assertEqual(len(bookings), 1)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под первого заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Должен смочь удалить заказ
        response = self.client.post(reverse('delete-booking',
                             kwargs={'pk': booking.id}),
                             follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        bookings = Booking.objects.all()
        self.assertEqual(len(bookings), 0)


    def test_performer_and_can_not_create_booking(self):
        """
        Создать пользователя - исполнитель.
        Ему должно не хватать прав для создания заказа.
        """
        user = User.objects.get(username='john')
        user_cash_before = user.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 403)

    def test_create_customer_and_performer_create_booking_serve_and_check_own_page(self):
        """
        Заказчик создает заказ.
        Другой берет его на выполнение.
        Первый подтверждает и завершает заказ.
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('own-booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('own-booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user = User.objects.get(username='john')

        # Подтверждение исполнителем взятия заказа заказчиком
        response = self.client.post(reverse('approve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.RUNNING)
        self.assertEqual(user1.profile.cash + booking.price, user1_cash_before)

        # Закрытие заказа
        response = self.client.post(reverse('complete-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Завершен
        user2 = User.objects.get(username='johndow')
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.COMPLETED)
        system_account = SystemAccount.objects.all()[0]
        comission = system_account.get_comission()
        self.assertEqual(system_account.account, booking.price * comission)
        self.assertEqual(user2.profile.cash, booking.price * (1 - comission))

    def test_customer_create_and_delete_booking(self):
        """
        Заказчик создает заказ.
        И удаляет его.
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Должен смочь удалить заказ
        response = self.client.post(reverse('delete-booking',
                             kwargs={'pk': booking.id}),
                             follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 0)

    def test_can_not_delete_waited_for_approving_booking(self):
        """
        Заказчик создает заказ.
        Другой берет его на выполнение.
        Первый подтверждает и завершает заказ.
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Ждет подтверждения взятия на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Попытка удаления заказа - нельзя при ждущем статусе
        response = self.client.post(reverse('delete-booking',
                             kwargs={'pk': booking.id }),
                             follow=True)
        self.assertEqual(response.status_code, 404)

        bookings = Booking.objects.all()
        self.assertEqual(len(bookings), 1)


    def test_can_not_remove_running_booking(self):
        """
        Заказчик создает заказ.
        Другой берет его на выполнение.
        Первый подтверждает и завершает заказ.
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под исполнителя
        response = self.client.post('/accounts/login/',
                                    {'username': 'johndow', 'password': 'dowpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user2 = User.objects.get(username='johndow')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взятие заказа на исполнение
        response = self.client.post(reverse('serve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Ждет подтверждения взятия на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_performer(), user2)
        self.assertEqual(booking.get_status(), Booking.WAITING_FOR_APPROVAL)

        # Выход
        response = self.client.post('/accounts/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/logged_out.html')

        # Вход из-под заказчика
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user = User.objects.get(username='john')

        # Подтверждение исполнителем взятия заказа заказчиком
        response = self.client.post(reverse('approve-booking'),
                                    {'booking': booking.id}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Взят на исполнение
        booking = Booking.objects.all()[0]
        self.assertEqual(booking.get_status(), Booking.RUNNING)
        self.assertEqual(user1.profile.cash + booking.price, user1_cash_before)

        # Попытка удаления заказа - нельзя при статусе running
        response = self.client.post(reverse('delete-booking',
                             kwargs={'pk': booking.id }),
                             follow=True)
        self.assertEqual(response.status_code, 404)

        bookings = Booking.objects.all()
        self.assertEqual(len(bookings), 1)

    def test_update_booking(self):
        """
        Проверка возможности обновления заказа
        """

        user1 = User.objects.get(username='john')
        user1_cash_before = user1.profile.cash

        # Вход
        response = self.client.post('/accounts/login/',
                                    {'username': 'john', 'password': 'johnpassword'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр списка заказов
        response = self.client.get(reverse('booking-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Просмотр формы создания заказа
        response = self.client.get(reverse('create-booking'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_form.html')

        # Создание заказа
        response = self.client.post(reverse('create-booking'),
                                    {'title': 'test_title1',
                                        'text': 'test_text1', 'price': '12.00'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        # Проверка того, что заказ в базе после создания
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        user1 = User.objects.get(username='john')

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title1')
        self.assertEqual(booking.text, 'test_text1')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)

        # Обновление заказа
        response = self.client.post(reverse('update-booking',
                                    kwargs={"pk": booking.id}),
                                    {'title': 'test_title2',
                                     'text': 'test_text2'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'booking/booking_list.html')

        user1 = User.objects.get(username='john')
        self.assertEqual(len(Booking.objects.all()), 1)
        booking = Booking.objects.all()[0]

        self.assertEqual(booking.get_customer(), user1)
        self.assertEqual(booking.title, 'test_title2')
        self.assertEqual(booking.text, 'test_text2')
        self.assertEqual(booking.price, 12.0)
        self.assertEqual(booking.status, Booking.PENDING)
