from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.utils.translation import ugettext as _

from avatar.forms import PrimaryAvatarForm, DeleteAvatarForm, UploadAvatarForm, CropAvatarForm
from avatar.models import Avatar
from avatar.settings import AVATAR_MAX_AVATARS_PER_USER, AVATAR_DEFAULT_SIZE, AVATAR_CROP_VIEW_SIZE, AVATAR_SEND_NOTIFICATIONS
from avatar.util import get_primary_avatar, get_default_avatar_url, invalidate_cache

notification = False
if AVATAR_SEND_NOTIFICATIONS and 'notification' in settings.INSTALLED_APPS:
    from notification import models as notification

friends = False
if 'friends' in settings.INSTALLED_APPS:
    friends = True
    from friends.models import Friendship

def _get_next(request):
    """
    The part that's the least straightforward about views in this module is how they 
    determine their redirects after they have finished computation.

    In short, they will try and determine the next place to go in the following order:

    1. If there is a variable named ``next`` in the *POST* parameters, the view will
    redirect to that variable's value.
    2. If there is a variable named ``next`` in the *GET* parameters, the view will
    redirect to that variable's value.
    3. If Django can determine the previous page from the HTTP headers, the view will
    redirect to that previous page.
    """
    next = request.POST.get('next', request.GET.get('next',
        request.META.get('HTTP_REFERER', None)))
    if not next:
        next = request.path
    return next
    
def _notification_updated(request, avatar):
    notification.send([request.user], "avatar_updated",
        {"user": request.user, "avatar": avatar})
    if friends:
        notification.send((x['friend'] for x in
                Friendship.objects.friends_for_user(request.user)),
            "avatar_friend_updated",
            {"user": request.user, "avatar": avatar}
        )

def _get_avatars(user):
    # Default set. Needs to be sliced, but that's it. Keep the natural order.
    avatars = user.avatar_set.all()
    
    # Current avatar
    primary_avatar = avatars.order_by('-primary')[:1]
    if primary_avatar:
        avatar = primary_avatar[0]
    else:
        avatar = None
    
    if AVATAR_MAX_AVATARS_PER_USER == 1:
        avatars = primary_avatar
    else:
        # Slice the default set now that we used the queryset for the primary avatar
        avatars = avatars[:AVATAR_MAX_AVATARS_PER_USER]
    return (avatar, avatars)    

@login_required
def add(request, extra_context=None, next_override=None,
        upload_form=UploadAvatarForm, *args, **kwargs):
    if extra_context is None:
        extra_context = {}
    avatar, avatars = _get_avatars(request.user)
    upload_avatar_form = upload_form(request.POST or None,
        request.FILES or None, user=request.user)
    if request.method == "POST" and 'avatar' in request.FILES:
        if upload_avatar_form.is_valid():
            avatar = Avatar(
                user = request.user,
                primary = True,
            )
            image_file = request.FILES['avatar']
            avatar.avatar.save(image_file.name, image_file)
            avatar.save()
            messages.success(request,
                             _("Successfully uploaded avatar.")
                             )
            if notification:
                _notification_updated(request, avatar)
            return HttpResponseRedirect(next_override or _get_next(request))
    return render_to_response(
        'avatar/add.html',
        extra_context,
        context_instance = RequestContext(
            request,
            { 'avatar': avatar, 
              'avatars': avatars, 
              'upload_avatar_form': upload_avatar_form,
              'next': next_override or _get_next(request), }
        )
    )

@login_required
def crop(request, avatar_id, extra_context=None, next_override=None,
        crop_form=CropAvatarForm, *args, **kwargs):
    if extra_context is None:
        extra_context = {}

    avatar = get_object_or_404(request.user.avatar_set, pk=avatar_id)
    crop_avatar_form = crop_form(request.POST or None)

    if request.method == "POST":
        if crop_avatar_form.is_valid():
            avatar.set_crop(request.POST)
            avatar.save()

            # Invalidate the cache to prevent wrong avatar appearing
            invalidate_cache(request.user)

            messages.success(request,
                             _("Successfully edited avatar.")
                             )

            if notification:
                _notification_updated(request, avatar)
            return HttpResponseRedirect(next_override or _get_next(request))
    
    (w, h) = (avatar.avatar.width, avatar.avatar.height)
    if w>h:
        d_w = AVATAR_CROP_VIEW_SIZE
        d_h = int(AVATAR_CROP_VIEW_SIZE * float(h)/w)
    else:
        d_w = int(AVATAR_CROP_VIEW_SIZE * float(w)/h)
        d_h = AVATAR_CROP_VIEW_SIZE

    return render_to_response(
        'avatar/crop.html',
        extra_context,
        context_instance = RequestContext(
            request,
            { 'avatar': avatar, 
              'crop_avatar_form': crop_avatar_form,
              'orig_size': (w, h),
              'display_size': (d_w, d_h),
              'preview_size': (AVATAR_DEFAULT_SIZE,AVATAR_DEFAULT_SIZE),
              'initial_crop': min(d_w, d_h),
              'next': next_override or _get_next(request), }
        )
    )


@login_required
def change(request, extra_context=None, next_override=None,
        upload_form=UploadAvatarForm, primary_form=PrimaryAvatarForm,
        *args, **kwargs):
    if extra_context is None:
        extra_context = {}
    avatar, avatars = _get_avatars(request.user)
    if avatar:
        kwargs = {'initial': {'choice': avatar.id}}
    else:
        kwargs = {}
    upload_avatar_form = upload_form(user=request.user, **kwargs)
    primary_avatar_form = primary_form(request.POST or None,
        user=request.user, avatars=avatars, **kwargs)
    if request.method == "POST":
        updated = False
        if 'choice' in request.POST and primary_avatar_form.is_valid():
            avatar = Avatar.objects.get(id=
                primary_avatar_form.cleaned_data['choice'])
            avatar.primary = True
            avatar.save()
            updated = True

            # Invalidate the cache to prevent wrong avatar appearing
            invalidate_cache(request.user)

            messages.success(request,
                             _("Successfully updated your avatar.")
                             )
        if updated and notification:
            _notification_updated(request, avatar)
        return HttpResponseRedirect(next_override or _get_next(request))
    return render_to_response(
        'avatar/change.html',
        extra_context,
        context_instance = RequestContext(
            request,
            { 'avatar': avatar, 
              'avatars': avatars,
              'upload_avatar_form': upload_avatar_form,
              'primary_avatar_form': primary_avatar_form,
              'next': next_override or _get_next(request), }
        )
    )

@login_required
def delete(request, extra_context=None, next_override=None, *args, **kwargs):
    if extra_context is None:
        extra_context = {}
    avatar, avatars = _get_avatars(request.user)
    delete_avatar_form = DeleteAvatarForm(request.POST or None,
        user=request.user, avatars=avatars)
    if request.method == 'POST':
        if delete_avatar_form.is_valid():
            ids = delete_avatar_form.cleaned_data['choices']
            if unicode(avatar.id) in ids and avatars.count() > len(ids):
                # Find the next best avatar, and set it as the new primary
                for a in avatars:
                    if unicode(a.id) not in ids:
                        a.primary = True
                        a.save()
                        if notification:
                            _notification_updated(request, a)
                        break
            Avatar.objects.filter(id__in=ids).delete()

            # Invalidate the cache to prevent wrong avatar appearing
            # when only one's left
            invalidate_cache(request.user)

            messages.success(request,
                             _("Successfully deleted the requested avatars.")
                             )
            return HttpResponseRedirect(next_override or _get_next(request))
    return render_to_response(
        'avatar/confirm_delete.html',
        extra_context,
        context_instance = RequestContext(
            request,
            { 'avatar': avatar, 
              'avatars': avatars,
              'delete_avatar_form': delete_avatar_form,
              'next': next_override or _get_next(request), }
        )
    )

@login_required
def change_crop_delete(request, *args, **kwargs):
    """
    Dispatch a command based on an action
    """
    if request.POST.get('change', False):
        change(request, *args, **kwargs)
        return redirect('avatar_change')
         
    elif request.POST.get('crop', False):
        return redirect('avatar_crop', request.POST.get('choice'))

    elif request.POST.get('delete', False):
        return redirect('avatar_delete')

    return redirect('avatar_change')
        
    
def render_primary(request, extra_context={}, user=None, size=AVATAR_DEFAULT_SIZE, *args, **kwargs):
    size = int(size)
    avatar = get_primary_avatar(user, size=size)
    if avatar:
        # FIXME: later, add an option to render the resized avatar dynamically
        # instead of redirecting to an already created static file. This could
        # be useful in certain situations, particulary if there is a CDN and
        # we want to minimize the storage usage on our static server, letting
        # the CDN store those files instead
        return HttpResponseRedirect(avatar.avatar_url(size))
    else:
        url = get_default_avatar_url()
        return HttpResponseRedirect(url)
    
