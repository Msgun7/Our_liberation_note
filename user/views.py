import os
import random
import string
from datetime import datetime

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from diary.models import Comment, Note, PhotoPage, PlanPage, Stamp
from diary.serializers import MarkerSerializer
from user.models import CheckEmail, User, UserGroup
from user.serializers import (
    GroupCreateSerializer,
    GroupSerializer,
    LoginSerializer,
    SignUpSerializer,
    UserUpdateSerializer,
    UserViewSerializer,
)

from .validators import check_password


# 이메일 전송
class SendEmail(APIView):
    def post(self, request):
        subject = "[우리들의 해방일지] 인증 코드를 확인해주세요!"
        user_email = request.data.get("email")
        random_code = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )  # 6자리 랜덤 문자열 생성
        body = f"이메일 확인 코드: {random_code}"  # 랜덤 코드 본문에 추가
        email = EmailMessage(
            subject,
            body,
            to=[user_email],
        )
        email.send()

        # 인증 코드 DB에 저장
        code = CheckEmail.objects.create(code=random_code, email=user_email)

        return Response(
            {"message": "이메일을 전송했습니다. 메일함을 확인하세요.", "code": code.id},
            status=status.HTTP_200_OK,
        )


# 회원 가입
class SignupView(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        password = request.data.get("password")
        password2 = request.data.get("password2")

        # 이메일 중복 확인
        try:
            user = User.objects.get(email=email)
            return Response(
                {"message": "이메일이 이미 존재합니다."}, status=status.HTTP_400_BAD_REQUEST
            )
        except ObjectDoesNotExist:
            pass

        # 가장 최근인 인증코드 인스턴스
        code_obj = (
            CheckEmail.objects.filter(email=email).order_by("-created_at").first()
        )
        print(code_obj)

        # 인증코드가 없는 경우
        if code_obj is None:
            return Response(
                {"message": "해당 메일로 보낸 인증 코드가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 인증 코드 유효 기간이 지난 경우
        if code_obj.expires_at < datetime.now():
            code_obj.delete()
            return Response(
                {"message": "인증 코드 유효 기간이 지났습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 인증 코드가 일치하지 않을 경우
        if code_obj.code != code:
            return Response(
                {"message": "인증 코드가 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 새 비밀번호 유효성 검사
        try:
            check_password(password)
        except ValidationError:
            return Response(
                {"message": "8자 이상의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 비밀번호와 비밀번호 확인 일치 여부 확인
        if password != password2:
            return Response(
                {"message": "비밀번호와 비밀번호 확인이 일치하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SignUpSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            code_obj.delete()  # 이메일 확인 코드 삭제
            return Response({"message": "가입완료!"}, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {"message": f"{serializer.errors}"}, status=status.HTTP_400_BAD_REQUEST
            )


# 로그인
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


# 유저 정보
class UserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # 회원 정보 보기
    def get(self, request):
        return Response(UserViewSerializer(request.user).data)

    # 회원 정보 수정
    def patch(self, request):
        current_password = request.data.get("check_password")
        user = User.objects.get(email=request.user)
        new_password = request.data.get("new_password")
        check_new_password = request.data.get("check_new_password")

        # 빈칸 유뮤 확인
        if new_password == "" or current_password == "" or check_new_password == "":
            return Response(
                {"message": " 빈칸을 입력해주세요!"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 비밀번호 일치 확인
        if new_password != check_new_password:
            return Response(
                {"message": "새로운 비밀번호가 일치하지 않습니다"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 기존 비밀번호와 check_password가 일치할 경우 회원정보(닉네임, 비밀번호) 수정
        if current_password and user.check_password(current_password):
            # 새로운 비밀번호의 유효성 검사
            try:
                check_password(new_password)
            except ValidationError:
                return Response(
                    {"message": "8자 이상의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다!"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = UserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid(raise_exception=True):
                # 비밀번호 변경한다면
                if new_password:
                    user.set_password(new_password)

                user.save()
                return Response({"message": "수정 완료!"}, status=status.HTTP_200_OK)
            else:
                return Response({serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(
                {"message": "비밀번호가 일치하지 않습니다"}, status=status.HTTP_400_BAD_REQUEST
            )

    # 회원 삭제
    def delete(self, request):
        user = request.user
        user.is_active = False
        user.save()
        return Response({"message": "계정 삭제 완료!"}, status=status.HTTP_204_NO_CONTENT)


# 비밀번호 새로 만들기
class ChangePassword(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        new_password = request.data.get("new_password")
        check_password_input = request.data.get("check_password")

        # 이메일 일치하는지 확인
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "비밀번호 찾기를 위한 이메일이 일치하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 가장 최근인 인증코드 인스턴스
        code_obj = (
            CheckEmail.objects.filter(email=email).order_by("-created_at").first()
        )

        # 인증코드가 없는 경우
        if code_obj is None:
            return Response(
                {"message": "해당 메일로 보낸 인증 코드가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 유효 기간 확인
        if code_obj.expires_at < datetime.now():
            # 인증 코드 유효 기간이 지난 경우
            code_obj.delete()
            return Response(
                {"message": "인증 코드 유효 기간이 지났습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 인증 코드 일치하는지 확인
        if code_obj.code != code:
            return Response(
                {"message": "이메일 확인 코드가 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 비밀번호와 비밀번호 확인 일치 여부 확인
        if new_password != check_password_input:
            return Response(
                {"message": "비밀번호와 비밀번호 확인이 일치하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 새 비밀번호 유효성 검사
        try:
            check_password(check_password_input)
        except ValidationError:
            return Response(
                {"message": "8자 이상의 영문 대/소문자, 숫자, 특수문자 조합이어야 합니다!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 비밀번호 업데이트
        user.set_password(new_password)
        user.save()

        # 인증코드 삭제
        code_obj.delete()
        return Response({"message": "비밀번호 변경 완료!"}, status=status.HTTP_200_OK)


class GroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        groups = UserGroup.objects.filter(members=request.user, status="0").order_by(
            "-created_at"
        )
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 그룹 만들기
    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)

        if serializer.is_valid():
            group_name = serializer.validated_data.get("name")

            # 이미 같은 이름의 그룹이 있는지 확인
            if UserGroup.objects.filter(name=group_name).exists():
                error_message = {"error": "이미 같은 이름의 그룹이 존재합니다."}
                return Response(error_message, status=status.HTTP_400_BAD_REQUEST)
            # 그룹 생성하면서 그룹장을 request.user로 설정
            group = serializer.save(master_id=request.user.id)
            # master를 멤버로 추가하기
            group.members.add(request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 그룹 삭제하기
    def delete(self, request):
        group_ids = request.data.get("group_ids")

        for id in group_ids:
            # 비활성 불러오기
            group = get_object_or_404(
                UserGroup.objects.filter(
                    id=id["id"], master_id=request.user.id, status__in=["1"]
                )
            )
            # 본인이 생성한 그룹이 맞다면
            if request.user == group.master:
                group.status = "3"
                group.save()

                # 그룹에 속한 노트, 계획, 사진첩, 댓글, 스탬프 상태 변경
                notes = Note.objects.filter(group=group)
                notes.update(status="3")

                plan_pages = PlanPage.objects.filter(diary__in=notes)
                plan_pages.update(status="3")

                photo_pages = PhotoPage.objects.filter(diary__in=notes)
                photo_pages.update(status="3")

                comments = Comment.objects.filter(photo__in=photo_pages)
                comments.update(status="3")

                stamps = Stamp.objects.filter(photo__in=photo_pages)
                stamps.update(status="3")

                status_code = status.HTTP_204_NO_CONTENT
                message = "그룹이 삭제되었습니다."

            # 본인이 생성한 그룹이 아니라면
            else:
                status_code = status.HTTP_403_FORBIDDEN
                message = "권한이 없습니다."

        return Response({"message": message}, status=status_code)


class GroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # 그룹 상세보기
    def get(self, request, group_id):
        group = get_object_or_404(
            UserGroup.objects.filter(id=group_id, members=request.user, status="0")
        )
        serializer = GroupSerializer(group)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 그룹 수정하기
    def patch(self, request, group_id):
        group = get_object_or_404(
            UserGroup.objects.filter(id=group_id, master_id=request.user.id, status="0")
        )
        # 본인이 생성한 그룹이 맞다면
        if request.user.id == group.master_id:
            serializer = GroupCreateSerializer(group, data=request.data, partial=True)
            if serializer.is_valid():
                new_name = serializer.validated_data.get("name")
                # 그룹명 중복 확인
                if (
                    UserGroup.objects.filter(name=new_name)
                    .exclude(id=group_id)
                    .exists()
                ):
                    error_message = {"message": "같은 이름의 그룹이 이미 존재합니다."}
                    return Response(
                        error_message,
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # 수정하면서 그룹장을 request.user로 설정
                group = serializer.save(master_id=request.user.id)
                # master를 멤버로 추가하기
                group.members.add(request.user)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # 본인이 생성한 그룹이 아니라면
        else:
            return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)


# 소셜 로그인
URI = "https://liberation-note.com"


# OAuth 인증 url
class SocialUrlView(APIView):
    def post(self, request):
        social = request.data.get("social", None)
        code = request.data.get("code", None)

        # 소셜 로그인 확인 여부
        if social is None:
            return Response(
                {"error": "소셜로그인이 아닙니다"}, status=status.HTTP_400_BAD_REQUEST
            )
        # 카카오
        elif social == "kakao":
            url = (
                "https://kauth.kakao.com/oauth/authorize?client_id="
                + os.environ.get("KAKAO_REST_API_KEY")
                + "&redirect_uri="
                + URI
                + "&response_type=code&prompt=login"
            )
            return Response({"url": url}, status=status.HTTP_200_OK)
        # 네이버
        elif social == "naver":
            url = (
                "https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id="
                + os.environ.get("SOCIAL_AUTH_NAVER_CLIENT_ID")
                + "&redirect_uri="
                + URI
                + "&state="
                + os.environ.get("STATE")
            )
            return Response({"url": url}, status=status.HTTP_200_OK)
        # 구글
        elif social == "google":
            client_id = os.environ.get("SOCIAL_AUTH_GOOGLE_CLIENT_ID")
            redirect_uri = URI

            url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=email%20profile"

            return Response({"url": url}, status=status.HTTP_200_OK)


# 카카오 소셜 로그인
class KakaoLoginView(APIView):
    def post(self, request):
        code = request.data.get("code")  # 카카오에서 인증 후 얻은 code

        # 네이버 API로 액세스 토큰 요청
        access_token = requests.post(
            "https://kauth.kakao.com/" + "oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": os.environ.get("KAKAO_REST_API_KEY"),
                "redirect_uri": URI,
                "code": code,  # 인증 후 얻은 코드
            },
        )

        # 발급 받은 토큰에서 access token만 추출
        access_token = access_token.json().get("access_token")

        # 카카오 API로 사용자 정보 요청
        user_data_request = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )
        user_datajson = user_data_request.json()
        user_data = user_datajson["kakao_account"]
        email = user_data["email"]

        try:
            # 사용자가 이미 존재하는 경우 (회원가입이 되어 있는 경우)
            user = User.objects.get(email=email)
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )
        except:
            # 사용자가 존재하지 않는 경우 회원 가입 진행
            user = User.objects.create_user(email=email)
            user.set_unusable_password()  # 비밀번호 생성 X
            user.save()
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )


# 네이버 소셜 로그인
class NaverLoginView(APIView):
    def post(self, request):
        code = request.data.get("code")
        client_id = os.environ.get("SOCIAL_AUTH_NAVER_CLIENT_ID")
        client_secret = os.environ.get("SOCIAL_AUTH_NAVER_SECRET")
        redirect_uri = URI

        # 네이버 API로 액세스 토큰 요청
        access_token_request = requests.post(
            "https://nid.naver.com/oauth2.0/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )

        access_token_json = access_token_request.json()
        # 발급 받은 토큰에서 access token만 추출
        access_token = access_token_json.get("access_token")

        # 네이버 API로 사용자 정보 요청
        user_data_request = requests.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        user_data_json = user_data_request.json()
        user_data = user_data_json.get("response")
        email = user_data.get("email")

        try:
            # 사용자가 이미 존재하는 경우 (회원가입이 되어 있는 경우)
            user = User.objects.get(email=email)
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )
        except:
            # 사용자가 존재하지 않는 경우 회원 가입 진행
            user = User.objects.create_user(email=email)
            user.set_unusable_password()  # 비밀번호 생성 X
            user.save()
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )


# 구글 소셜 로그인
class GoogleLoginView(APIView):
    def post(self, request):
        code = request.data.get("code")
        client_id = os.environ.get("SOCIAL_AUTH_GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("SOCIAL_AUTH_GOOGLE_SECRET")
        redirect_uri = URI

        # 구글 API로 액세스 토큰 요청
        access_token_request = requests.post(
            "https://oauth2.googleapis.com/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "scope": "email",
            },
        )
        access_token_json = access_token_request.json()
        access_token = access_token_json.get("access_token")

        # 구글 API로 사용자 정보 요청
        user_data_request = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_data_json = user_data_request.json()
        email = user_data_json.get("email")

        try:
            # 사용자가 이미 존재하는 경우 (회원가입이 되어 있는 경우)
            user = User.objects.get(email=email)
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )
        except:
            # 사용자가 존재하지 않는 경우 회원 가입 진행
            user = User.objects.create_user(email=email)
            user.set_unusable_password()  # 비밀번호 생성 X
            user.save()
            refresh = RefreshToken.for_user(user)
            refresh["email"] = user.email
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )


class MyPageView(APIView):
    def get(self, request):
        profile = get_object_or_404(User, id=request.user.id)
        stamp = Stamp.objects.filter(user=request.user.id)
        group = UserGroup.objects.filter(members=request.user.id, status=0)
        profileserializer = UserViewSerializer(profile)
        stampserializer = MarkerSerializer(stamp, many=True)
        groupserializer = GroupSerializer(group, many=True)
        data = {
            "profile": profileserializer.data,
            "stamps": stampserializer.data,
            "groups": groupserializer.data,
        }
        return Response(data, status=status.HTTP_200_OK)


# 유저 리스트
class UserListView(generics.ListAPIView):
    serializer_class = UserViewSerializer

    def get_queryset(self):
        usersearch = self.request.query_params.get("usersearch", None)  # 유저 검색어 가져오기
        queryset = User.objects.all()

        # 이메일 필드에서 검색어가 포함된 사용자 찾기
        if usersearch is not None:
            queryset = queryset.filter(Q(email__icontains=usersearch)).distinct()

        return queryset.distinct()  # 중복 제거하여 반환
