# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django.contrib import admin
try:
    from django.contrib.contenttypes.fields import GenericRelation
except ImportError:
    from django.contrib.contenttypes import GenericRelation
from django.db import models
from django.utils.timezone import now

from pennyblack import settings
from pennyblack.options import (NewsletterReceiverMixin,
                                JobUnitMixin, JobUnitAdmin)
from pennyblack.models import Newsletter
from pennyblack.module.subscriber.views import unsubscribe


class NewsletterSubscriberManager(models.Manager):
    """
    Custom manager for NewsletterSubscriber to provide extra functionality
    """
    use_for_related_fields = True

    def get_or_add(self, email, **kwargs):
        """
        Gets a subscriber, if he doesn't exist it creates him.
        """
        try:
            return self.get(email__iexact=email)
        except self.model.DoesNotExist:
            return self.create(email=email.lower(), **kwargs)

    def active(self):
        """
        Gives only the active subscribers
        """
        return self.filter(is_active=True)

newsletter_subscriber_manager = NewsletterSubscriberManager()


class NewsletterSubscriber(models.Model, NewsletterReceiverMixin):
    """
    A generic newsletter subscriber
    """
    # from pennyblack.models.mail import Mail
    email = models.EmailField(
        verbose_name=_("email address"),
        unique=True)
    groups = models.ManyToManyField(
        'subscriber.SubscriberGroup',
        verbose_name=_("Groups"),
        related_name='subscribers')
    date_subscribed = models.DateTimeField(
        verbose_name=_("Subscribe Date"),
        default=now)
    mails = GenericRelation('pennyblack.Mail')
    is_active = models.BooleanField(
        verbose_name=_("Active"),
        default=True)

    objects = newsletter_subscriber_manager
    default_manager = newsletter_subscriber_manager

    class Meta:
        verbose_name = _("Subscriber")
        verbose_name_plural = _("Subscribers")
        app_label = "subscriber"

    def __unicode__(self):
        return self.email

    def on_bounce(self, mail):
        """
        A mail got bounced, consider deactivating this subscriber.
        """
        bounce_count = 0
        for mail in self.mails.order_by('pk'):
            bounce_count += mail.bounced
            if mail.viewed:
                bounce_count = 0
        if bounce_count >= settings.SUBSCRIBER_BOUNCES_UNTIL_DEACTIVATION:
            self.is_active = False
            self.save()

    def unsubscribe(self):
        self.is_active = False
        self.save()

    @classmethod
    def register_extension(cls, register_fn):
        """
        Call the register function of an extension. You must override this
        if you provide a custom ModelAdmin class and want your extensions to
        be able to patch stuff in.
        """
        register_fn(cls, NewsletterSubscriberAdmin)


class NewsletterSubscriberAdmin(admin.ModelAdmin):
    search_fields = ('email',)
    list_filter = ('groups', 'is_active')
    list_display = ('__unicode__', 'is_active')
    filter_horizontal = ('groups',)


class SubscriberGroupManager(models.Manager):
    """
    Custom manager for SubscriberGroup to provide extra functionality
    """
    def get_or_add(self, name, **kwargs):
        """
        Gets a group, if she doesn't exist it creates her.
        """
        try:
            return self.get(name__iexact=name)
        except self.model.DoesNotExist:
            return self.create(name=name, **kwargs)


class SubscriberGroup(models.Model, JobUnitMixin):
    """
    Groups to add newsletter subscribers
    """
    name = models.CharField(
        max_length=50,
        verbose_name=_("Name"),
        unique=True)

    objects = SubscriberGroupManager()

    class Meta:
        verbose_name = _("Subscriber Group")
        verbose_name_plural = _("Subscriber Groups")
        app_label = "subscriber"

    def __unicode__(self):
        return self.name

    @property
    def member_count(self):
        return self.subscribers.active().count()

    def get_member_count(self):
        return self.member_count
    get_member_count.short_description = _("Member Count")

    def get_newsletter_receiver_collections(self):
        """
        Every Group has only one collection
        """
        return (('all', {}),)

    def get_receiver_queryset(self):
        """
        Return all group members
        """
        return self.subscribers.active()


class SubscriberGroupAdmin(JobUnitAdmin):
    list_display = ('__unicode__', 'get_member_count')

# register view links
Newsletter.register_view_link('subscriber.unsubscribe', unsubscribe)
