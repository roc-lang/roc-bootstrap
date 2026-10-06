; RUN: opt -passes=always-inline -verify-each -S %s | FileCheck %s
;
; Splitting a call block by moving its prefix must preserve entry references,
; including blockaddresses, and outgoing/self-loop PHI edges. The second call
; block has a longer prefix so the suffix is moved instead.

@loop_address = global ptr blockaddress(@prefix, %loop)
; CHECK: @loop_address = global ptr blockaddress(@prefix, %loop)

declare void @side(i32)

define internal i32 @callee(i32 %x) alwaysinline {
entry:
  %zero = icmp eq i32 %x, 0
  br i1 %zero, label %yes, label %no
yes:
  call void @side(i32 1)
  ret i32 1
no:
  call void @side(i32 2)
  ret i32 2
}

; CHECK-LABEL: define i32 @prefix(
; CHECK: entry:
; CHECK-NEXT: br label %loop
; CHECK: loop:
; CHECK-NEXT: %i = phi i32 [ 0, %entry ], [ %next, %callee.exit ]
; CHECK: br i1 %zero.i, label %yes.i, label %no.i
; CHECK: callee.exit:
; CHECK-NEXT: %r{{[0-9]*}} = phi i32
; CHECK: br i1 %again, label %loop, label %merge
; CHECK: merge:
; CHECK-NEXT: %out = phi i32 [ %a4, %callee.exit ]
; CHECK-NEXT: ret i32 %out
define i32 @prefix(i32 %x, i32 %n) {
entry:
  br label %loop
loop:
  %i = phi i32 [ 0, %entry ], [ %next, %loop ]
  %r = call i32 @callee(i32 %x)
  %a1 = add i32 %r, %i
  %a2 = xor i32 %a1, %x
  %a3 = mul i32 %a2, 3
  %a4 = add i32 %a3, 4
  %next = add i32 %i, 1
  %again = icmp ult i32 %next, %n
  br i1 %again, label %loop, label %merge
merge:
  %out = phi i32 [ %a4, %loop ]
  ret i32 %out
}

; CHECK-LABEL: define i32 @suffix(
; CHECK: entry:
; CHECK-NEXT: %a1 = add i32 %x, 1
; CHECK: %a4 = add i32 %a3, 4
; CHECK: br i1 %zero.i, label %yes.i, label %no.i
; CHECK: callee.exit:
; CHECK-NEXT: %r{{[0-9]*}} = phi i32
; CHECK-NEXT: ret i32 %r
define i32 @suffix(i32 %x) {
entry:
  %a1 = add i32 %x, 1
  %a2 = xor i32 %a1, %x
  %a3 = mul i32 %a2, 3
  %a4 = add i32 %a3, 4
  %r = call i32 @callee(i32 %x)
  ret i32 %r
}
